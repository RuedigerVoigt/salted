Versions shown are the **minimum** each constraint allows, not the versions that
happen to be installed anywhere. For salted's own dependencies they are the floors
declared in `pyproject.toml`; for everything below them they are derived from the
constraint on the edge that pulls them in. Installing today resolves to newer
versions than these — this graph answers "what is the oldest set salted claims to
work with", which is what a lower-bound bump has to be checked against.

```mermaid
flowchart TD
    classDef missing stroke-dasharray: 5
    classDef optional fill:#e8e8e8,stroke:#aaaaaa,color:#777777,stroke-dasharray:4
    aiodns["aiodns<br/>4.0.4"]
    aiohappyeyeballs["aiohappyeyeballs<br/>2.5.0"]
    aiohttp["aiohttp<br/>3.14.3"]
    aiosignal["aiosignal<br/>1.4.0"]
    attrs["attrs<br/>17.3.0"]
    beautifulsoup4["beautifulsoup4<br/>4.15.0"]
    cffi["cffi<br/>2.0.0b1"]
    colorama["colorama<br/>any"]
    compatibility["compatibility<br/>2.2.0"]
    frozenlist["frozenlist<br/>1.1.1"]
    idna["idna<br/>2.0"]
    jinja2["Jinja2<br/>3.1.6"]
    latexcodec["latexcodec<br/>1.0.4"]:::optional
    markupsafe["MarkupSafe<br/>2.0"]
    multidict["multidict<br/>4.5"]
    propcache["propcache<br/>0.2.1"]
    pybtex["pybtex<br/>0.26.1"]:::optional
    pycares["pycares<br/>5.0.0"]
    pycparser["pycparser<br/>any"]
    pyyaml["PyYAML<br/>3.01"]:::optional
    salted["salted<br/>2.0.0"]
    soupsieve["soupsieve<br/>1.6.1"]
    tqdm["tqdm<br/>4.70.0"]
    typing-extensions["typing_extensions<br/>4.0.0"]
    userprovided["userprovided<br/>2.6.0"]
    yarl["yarl<br/>1.17.0"]
    lxml["lxml<br/>6.1.2"]:::optional
    aiodns -- ">=5.0.0,<6" --> pycares
    aiohttp -- ">=0.2.0" --> propcache
    aiohttp -- ">=1.1.1" --> frozenlist
    aiohttp -- ">=1.17.0,<2.0" --> yarl
    aiohttp -- ">=1.4.0" --> aiosignal
    aiohttp -- ">=17.3.0" --> attrs
    aiohttp -- ">=2.5.0" --> aiohappyeyeballs
    aiohttp -- ">=4.5,<7.0" --> multidict
    aiosignal -- ">=1.1.0" --> frozenlist
    beautifulsoup4 -- ">=1.6.1" --> soupsieve
    beautifulsoup4 -- ">=4.0.0" --> typing-extensions
    cffi -- "any" --> pycparser
    jinja2 -- ">=2.0" --> markupsafe
    pybtex -. ">=1.0.4" .-> latexcodec
    pybtex -. ">=3.01" .-> pyyaml
    pycares -- ">=2.0.0b1" --> cffi
    salted -- ">=2.2.0" --> compatibility
    salted -- ">=2.6.0" --> userprovided
    salted -- ">=3.1.6" --> jinja2
    salted -- ">=3.14.3" --> aiohttp
    salted -- ">=4.0.4" --> aiodns
    salted -- ">=4.15.0" --> beautifulsoup4
    salted -- ">=4.70.0" --> tqdm
    tqdm -- "any" --> colorama
    yarl -- ">=0.2.1" --> propcache
    yarl -- ">=2.0" --> idna
    yarl -- ">=4.0" --> multidict
    salted -. ">=6.1.2" .-> lxml
    salted -. ">=0.26.1" .-> pybtex
```

Solid arrows are installed by `pip install salted`. Dotted arrows and greyed nodes
are optional extras: `salted[lxml]`, `salted[bibtex]`, or `salted[all]` for both.
Note that `latexcodec` and `PyYAML` reach a default install through nothing else —
they arrive only with `pybtex`.

Where two parents constrain the same package, the higher floor wins: `propcache` is
`>=0.2.1` (yarl) rather than `>=0.2.0` (aiohttp), and `frozenlist` is `>=1.1.1`
(aiohttp) rather than `>=1.1.0` (aiosignal). `colorama` and `pycparser` are pulled in
without a lower bound at all.
