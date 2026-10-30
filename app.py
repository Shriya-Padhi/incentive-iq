"""Chainlit UI: an incentive assistant for An Electrification Company's dealers.

Run with: chainlit run app.py -w
"""

import chainlit as cl
from chainlit.input_widget import Select
from dotenv import load_dotenv

from rag import answer, load_catalog, make_client, model_name
from retriever import NATIONWIDE, list_regions

load_dotenv()

INCOME_TIERS = ["Not specified", "Low income (under 80% AMI)", "Moderate income (80-150% AMI)", "Above 150% AMI"]
DEFAULTS = {"product": "EC-HP36-CC", "region": "Sacramento, CA", "income": "Moderate income (80-150% AMI)"}


@cl.set_starters
async def starters():
    return [
        cl.Starter(label="What can this product get here?",
                   message="Which incentives can my selected product get here, how much, and what paperwork is needed?"),
        cl.Starter(label="Is the federal tax credit still available?",
                   message="Can my customer still claim the federal tax credit for a heat pump installed this year?"),
        cl.Starter(label="Are state rebates open?",
                   message="Are income-qualified state heat pump rebates open right now, or waitlisted?"),
    ]


@cl.on_chat_start
async def start():
    products = [row["model"] for row in load_catalog()]
    regions = [r for r in list_regions() if r != NATIONWIDE] or ["Sacramento, CA"]
    settings = await cl.ChatSettings([
        Select(id="product", label="Product (fictional sample catalog)", values=products,
               initial_index=products.index(DEFAULTS["product"]) if DEFAULTS["product"] in products else 0),
        Select(id="region", label="Customer location", values=regions,
               initial_index=regions.index(DEFAULTS["region"]) if DEFAULTS["region"] in regions else 0),
        Select(id="income", label="Household income tier", values=INCOME_TIERS,
               initial_index=INCOME_TIERS.index(DEFAULTS["income"])),
    ]).send()
    cl.user_session.set("settings", settings)
    cl.user_session.set("client", make_client())


@cl.on_settings_update
async def update_settings(settings):
    cl.user_session.set("settings", settings)
    await cl.Message(
        content=f"Now answering for **{settings['product']}** in **{settings['region']}** "
                f"({settings['income']})."
    ).send()


def format_sources(sources: list[dict]) -> str:
    if not sources:
        return ""
    lines = ["\n\n**Sources**"]
    for s in sources:
        lines.append(f"[{s['n']}] [{s['program']}]({s['url']}), fetched {s['fetched_at']}")
    return "\n".join(lines)


@cl.on_message
async def on_message(message: cl.Message):
    settings = cl.user_session.get("settings")
    question = message.content
    if settings["product"].upper() not in question.upper():
        question += f" (Product: {settings['product']})"
    income = None if settings["income"] == "Not specified" else settings["income"]

    try:
        result = await cl.make_async(answer)(
            question, cl.user_session.get("client"), model_name(),
            region=settings["region"], income_tier=income,
        )
    except Exception as exc:  # model or database errors
        await cl.Message(content=f"Something went wrong: {exc}. Is Ollama running, and did you run ingest.py?").send()
        return

    async with cl.Step(name="retrieved sources", type="retrieval") as step:
        step.input = f"{question}\nRegion filter: {settings['region']}"
        step.output = "\n\n".join(
            f"[{i}] score {h['score']:.2f} | {h['program']} ({h['region']})\n{h['text'][:300]}..."
            for i, h in enumerate(result["hits"], 1)
        ) or "No sufficiently relevant passages found."

    await cl.Message(content=result["answer"] + format_sources(result["sources"])).send()