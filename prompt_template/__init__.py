import os
from pathlib import Path

# in prompt_template/__init__.py

# Locate THIS file's directory
here = Path(__file__).parent

with open(here /"json2text.md") as f:
    prompt_json2text = f.read()
    f.close()

with open(here /"isCheeseChat.md") as f:
    isCheeseChat = f.read()
    f.close()

with open(here /"query2filter.md") as f:
    query2filter = f.read()
    f.close()

with open(here /"query2mongo.md") as f:
    query2mongo = f.read()
    f.close()

with open(here /"system.md") as f:
    system = f.read()
    f.close()

with open(here /"hello.md") as f:
    hello = f.read()
    f.close()

with open(here /"general.md") as f:
    general = f.read()
    f.close()

with open(here /"isPossibleQuery.md") as f:
    isPossibleQuery = f.read()
    f.close()

with open(here / "compare_with_requery.md") as f:
    compare_with_requery = f.read()
    f.close()

with open(here / "reasoner.md") as f:
    reasoner = f.read()
    f.close()