```mermaid
flowchart TD
    classDef missing stroke-dasharray: 5
    classDef optional fill:#e8e8e8,stroke:#aaaaaa,color:#777777,stroke-dasharray:4
    aiodns["aiodns<br/>4.0.0"]
    aiohappyeyeballs["aiohappyeyeballs<br/>2.6.1"]
    aiohttp["aiohttp<br/>3.13.5"]
    aiosignal["aiosignal<br/>1.4.0"]
    attrs["attrs<br/>25.4.0"]
    beautifulsoup4["beautifulsoup4<br/>4.14.3"]
    cffi["cffi<br/>2.0.0"]
    colorama["colorama<br/>0.4.6"]
    compatibility["compatibility<br/>2.0.0"]
    frozenlist["frozenlist<br/>1.8.0"]
    idna["idna<br/>3.11"]
    jinja2["Jinja2<br/>3.1.6"]
    latexcodec["latexcodec<br/>3.0.1"]
    markupsafe["MarkupSafe<br/>3.0.3"]
    multidict["multidict<br/>6.7.0"]
    propcache["propcache<br/>0.4.1"]
    pybtex["pybtex<br/>0.26.1"]
    pycares["pycares<br/>5.0.1"]
    pycparser["pycparser<br/>2.23"]
    pyyaml["PyYAML<br/>6.0.3"]
    salted["salted<br/>2.0.0"]
    soupsieve["soupsieve<br/>2.8"]
    tqdm["tqdm<br/>4.67.3"]
    typing-extensions["typing_extensions<br/>4.15.0"]
    userprovided["userprovided<br/>2.3.0"]
    yarl["yarl<br/>1.22.0"]
    lxml["lxml<br/>6.1.0"]:::optional
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
    pybtex -- ">=1.0.4" --> latexcodec
    pybtex -- ">=3.01" --> pyyaml
    pycares -- ">=2.0.0b1" --> cffi
    salted -- ">=0.26.1" --> pybtex
    salted -- ">=2.0.0" --> compatibility
    salted -- ">=2.3.0" --> userprovided
    salted -- ">=3.1.6" --> jinja2
    salted -- ">=3.13.5" --> aiohttp
    salted -- ">=4.0.0" --> aiodns
    salted -- ">=4.14.3" --> beautifulsoup4
    salted -- ">=4.67.3" --> tqdm
    tqdm -- "any" --> colorama
    yarl -- ">=0.2.1" --> propcache
    yarl -- ">=2.0" --> idna
    yarl -- ">=4.0" --> multidict
    salted -. ">=6.1.0" .-> lxml
```
