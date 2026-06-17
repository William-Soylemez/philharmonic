# python src/name_clusters.py --api_key {params.api_key} -o {output.human_readable} --go_db {input.go_database} -cfp {input.clusters}
import json
import os
import random
import shlex
import subprocess as sp
import time

import regex as re
import typer
from loguru import logger
from tqdm import tqdm

from .utils import load_cluster_json, parse_GO_database, print_cluster

app = typer.Typer()

task_instruction = """
You are an expert biologist with a deep understanding of the Gene Ontology. Your job is to give short, intuitive, high-level names to clusters of proteins, given a set of GO terms associated with the proteins and their frequencies.
"""

confidence_score = """
In addition to the name, you should indicate how confident you are that your label is correct, and that it is representative of the function of the cluster. This score should be None, Low, Medium, or High. If you cannot find a connection between the functions in the cluster, give a name of Unknown with a confidence of None.
"""

format_instruction = """
Your response should start with only the name of the cluster on the first line. Then, provide a short paragraph including your explanation for why you gave the cluster that name. Finally, on a new line, provide your confidence score. You should not put blank lines between these sections.
"""

analytical_approach = """
You should try to be as specific as possible in your naming, to avoid overlapping names with other similar clusters. However, the names should still be short and human readable, ideally fewer than 10 words. You should consider the most common GO terms in the cluster, and try to find a common theme or function that ties them together. If you cannot find a common theme, you should give the cluster a name of Unknown.
"""

one_shot_example = """
For example, given the cluster description below:

Cluster of 14 [pdam_00002129-RA,pdam_00001718-RA,...] (hash 1332063120138743063)
Triangles: 27.0
Max Degree: 8
Top Terms:
    GO:0071502 - <cellular response to temperature stimulus> (11)
    GO:0019233 - <sensory perception of pain> (11)
    GO:0042493 - <response to drug> (10)
    GO:0007603 - <phototransduction, visible light> (10)
    GO:0004876 - <complement component C3a receptor activity> (9)

We would name this cluster Temperature, Pain, and Drug Response because there is a high representation for GO terms related to temperature, drug, and pain response.
"""

request = """
Please name the following cluster:
"""

LLM_SYSTEM_TEMPLATE = (
    task_instruction
    + confidence_score
    + format_instruction
    + analytical_approach
    + one_shot_example
    + request
)


# Substrings that mark a (retryable) rate-limit / transient-overload response
# from the LLM provider. The `llm` CLI surfaces the provider's error text on
# stderr, so we match against that.
RATE_LIMIT_SIGNATURES = (
    "rate limit",
    "rate_limit",
    "ratelimit",
    "429",
    "too many requests",
    "quota",
    "overloaded",
    "temporarily unavailable",
    "please try again",
    "service unavailable",
    "503",
)

# llm_confidence value that marks a previously failed naming attempt. The model
# itself only ever emits None/Low/Medium/High (and a *name* of "Unknown" with
# confidence None for no-connection clusters), so a confidence of exactly
# "Unknown" is unambiguously our own failure sentinel from the except branch
# below. Re-runs use this to re-call the LLM only for calls that failed before.
FAILED_CONFIDENCE = "unknown"


def _is_rate_limit_error(message: str) -> bool:
    msg = message.lower()
    return any(sig in msg for sig in RATE_LIMIT_SIGNATURES)


def _call_llm(description, model, api_key):
    """Single invocation of the `llm` CLI; raises ChildProcessError on stderr."""
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    cmd = f"llm --system '{LLM_SYSTEM_TEMPLATE}' -m {model} '{description}' "

    proc = sp.Popen(shlex.split(cmd), stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = proc.communicate()
    if err.decode("utf-8") != "":
        raise ChildProcessError(err.decode("utf-8"))
    return out.decode("utf-8")


def llm_name_cluster(
    description,
    model="4o-mini",
    api_key=None,
    max_retries=6,
    base_delay=5.0,
    max_delay=120.0,
):
    """Name a cluster with the LLM.

    Retries on rate-limit / transient-overload errors with exponential backoff
    plus jitter, so a burst of clusters doesn't get throttled into "Unknown".
    Non-rate-limit errors are raised immediately for the caller to handle.
    """
    attempt = 0
    while True:
        try:
            output = _call_llm(description, model, api_key)
            break
        except ChildProcessError as e:
            if not _is_rate_limit_error(str(e)) or attempt >= max_retries:
                raise
            backoff = min(max_delay, base_delay * (2**attempt))
            # Equal jitter: wait at least half the backoff, up to the full amount.
            delay = backoff / 2 + random.uniform(0, backoff / 2)
            attempt += 1
            logger.warning(
                f"Rate limited by LLM API (attempt {attempt}/{max_retries}); "
                f"backing off {delay:.1f}s before retrying."
            )
            time.sleep(delay)

    reg = re.compile(r"(.*$)\s+(.*$)\s+(.*$)", re.MULTILINE)
    regsearch = reg.search(output)
    name = regsearch.group(1)
    explanation = regsearch.group(2)
    confidence = regsearch.group(3)

    logger.info(f"Name: {name}")
    logger.info(f"Explanation: {explanation}")
    logger.info(f"Confidence: {confidence}")

    return name, explanation, confidence


def _needs_naming(clust: dict, force: bool) -> bool:
    """Whether a cluster should be (re)named.

    Fresh clusters (no llm_name) are always named. Re-running over an
    already-described clusters.json re-calls the LLM only for clusters whose
    previous attempt failed (llm_confidence == "Unknown"), so a redo is cheap.
    `force` re-names everything.
    """
    if force:
        return True
    if "llm_name" not in clust:
        return True
    return str(clust.get("llm_confidence", "")).strip().lower() == FAILED_CONFIDENCE


@app.command()
def main(
    output: str = typer.Option(..., "-o", "--output", help="Output file"),
    json_output: str = typer.Option(None, "-j", "--json", help="Output in JSON format"),
    cluster_file_path: str = typer.Option(
        ..., "-cfp", "--cluster-file-path", help="Cluster file"
    ),
    go_db: str = typer.Option(..., "--go_db", help="GO database"),
    llm_name: bool = typer.Option(
        False, help="Use a large language model to name clusters"
    ),
    model: str = typer.Option("Meta-Llama-3-8B-Instruct", help="Language model to use"),
    api_key: str = typer.Option(None, help="OpenAI API key"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-name every cluster, even ones already named with a confident result.",
    ),
    max_retries: int = typer.Option(
        6, help="Max retries on LLM API rate-limit errors (exponential backoff)."
    ),
    retry_base_delay: float = typer.Option(
        5.0, help="Base seconds for rate-limit backoff."
    ),
    retry_max_delay: float = typer.Option(
        120.0, help="Max seconds for a single rate-limit backoff wait."
    ),
):
    """Summarize clusters"""
    clusters = load_cluster_json(cluster_file_path)
    go_database = parse_GO_database(go_db)

    if llm_name:
        for _, clust in tqdm(clusters.items()):
            if _needs_naming(clust, force):
                # Drop any stale fields from a prior failed attempt so they don't
                # leak into the description we send to the LLM.
                for k in ("llm_name", "llm_explanation", "llm_confidence"):
                    clust.pop(k, None)
                hr = print_cluster(clust, go_database, return_str=True)
                try:
                    name, explanation, confidence = llm_name_cluster(
                        hr,
                        model=model,
                        api_key=api_key,
                        max_retries=max_retries,
                        base_delay=retry_base_delay,
                        max_delay=retry_max_delay,
                    )
                    clust["llm_name"] = name
                    clust["llm_explanation"] = explanation
                    clust["llm_confidence"] = confidence
                except Exception as e:
                    logger.error(f"Error: {e}")
                    clust["llm_name"] = "Unknown"
                    clust["llm_explanation"] = "Unknown"
                    clust["llm_confidence"] = "Unknown"

            clust["human_readable"] = print_cluster(
                clust, go_database, return_str=True
            )
    else:
        for _, clust in tqdm(clusters.items()):
            clust["human_readable"] = print_cluster(clust, go_database, return_str=True)

    if json_output:
        with open(json_output, "w") as f:
            json.dump(clusters, f, indent=4)

    with open(output, "w") as f:
        for _, clust in clusters.items():
            description_string = print_cluster(clust, go_database, return_str=True)
            f.write(str(description_string))
            f.write("\n\n")


if __name__ == "__main__":
    app()
