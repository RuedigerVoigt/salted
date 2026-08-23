#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Tests that the dependency documentation matches pyproject.toml
~~~~~~~~~~~~~~~~~~~~~
Smart, Asynchronous Link Tester with Database backend (SALTED)
Source: https://github.com/RuedigerVoigt/salted
(c) 2020-2026: Released under the Apache License 2.0

Nothing else compares the published dependency graph to the actual
requirements, so the two drift apart silently: a floor raised in
pyproject.toml alone leaves the published graph naming a version salted
no longer supports. These tests make that drift a test failure.

The graph is generated into dependency-graph-diagram.md by
scripts/generate_dependency_graph.py; the prose about it lives in
dependency-graph.md and is not machine-checked.
"""

import pathlib
import re
import tomllib

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / 'pyproject.toml'
GRAPH = REPO_ROOT / 'documentation' / 'dependency-graph-diagram.md'
GRAPH_PROSE = REPO_ROOT / 'documentation' / 'dependency-graph.md'

# 'salted -- ">=2.2.0" --> compatibility'  (required, solid arrow)
# 'salted -. ">=6.1.1" .-> lxml'           (optional, dotted arrow)
_EDGE = re.compile(
    r'^\s*([\w-]+) (--|-\.) "([^"]*)" (-->|\.->) ([\w-]+)\s*$', re.MULTILINE)
# 'compatibility["compatibility<br/>2.2.0"]' with an optional ':::optional'
_NODE = re.compile(
    r'^\s*([\w-]+)\["([^"<]+)<br/>([^"]+)"\](:::\w+)?\s*$', re.MULTILINE)


def _normalize(name: str) -> str:
    """Compare package names case-insensitively (Jinja2 vs jinja2)."""
    return name.strip().lower()


@pytest.fixture(scope='module')
def graph_text() -> str:
    assert GRAPH.is_file(), f'missing {GRAPH}'
    return GRAPH.read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def nodes(graph_text) -> dict:
    """Map node id -> {'version': str, 'optional': bool}."""
    found = {}
    for node_id, _label, version, css in _NODE.findall(graph_text):
        found[_normalize(node_id)] = {
            'version': version.strip(),
            'optional': css == ':::optional',
        }
    assert found, 'no nodes parsed from the graph'
    return found


@pytest.fixture(scope='module')
def edges(graph_text) -> list:
    """List of (source, target, constraint, is_dotted)."""
    found = [
        (_normalize(src), _normalize(dst), constraint.strip(),
         open_style == '-.' and close_style == '.->')
        for src, open_style, constraint, close_style, dst
        in _EDGE.findall(graph_text)
    ]
    assert found, 'no edges parsed from the graph'
    return found


@pytest.fixture(scope='module')
def requirements() -> dict:
    """Map package name -> {'floor': str, 'optional': bool} from pyproject."""
    data = tomllib.loads(PYPROJECT.read_text(encoding='utf-8'))['project']
    result = {}
    for spec in data['dependencies']:
        name, _, floor = spec.partition('>=')
        result[_normalize(name)] = {'floor': floor.strip(), 'optional': False}
    for extra in data.get('optional-dependencies', {}).values():
        for spec in extra:
            name, _, floor = spec.partition('>=')
            # 'all' repeats what the single-feature extras already declare.
            result.setdefault(
                _normalize(name), {'floor': floor.strip(), 'optional': True})
    return result


@pytest.fixture(scope='module')
def salted_edges(edges) -> dict:
    """Map target -> (constraint, is_dotted) for edges starting at salted."""
    return {dst: (constraint, dotted)
            for src, dst, constraint, dotted in edges if src == 'salted'}


class TestGraphMatchesPyproject:
    """The salted -> X edges must mirror pyproject.toml exactly"""

    def test_every_requirement_has_an_edge(self, requirements, salted_edges):
        """A dependency added to pyproject must appear in the graph"""
        missing = set(requirements) - set(salted_edges)
        assert not missing, f'not drawn in the graph: {sorted(missing)}'

    def test_no_edges_without_a_requirement(self, requirements, salted_edges):
        """A dependency removed from pyproject must leave the graph"""
        orphans = set(salted_edges) - set(requirements)
        assert not orphans, f'no longer in pyproject.toml: {sorted(orphans)}'

    def test_edge_constraints_match_the_floors(self, requirements,
                                               salted_edges):
        """A raised floor must be raised in the graph too"""
        for name, spec in requirements.items():
            constraint, _dotted = salted_edges[name]
            assert constraint == f">={spec['floor']}", (
                f'{name}: pyproject says >={spec["floor"]}, '
                f'graph says {constraint}')

    def test_node_versions_are_the_floors(self, requirements, nodes):
        """Node labels show the lowest allowed version, not a resolved one"""
        for name, spec in requirements.items():
            assert name in nodes, f'{name} has no node'
            assert nodes[name]['version'] == spec['floor'], (
                f'{name}: node shows {nodes[name]["version"]}, '
                f'floor is {spec["floor"]}')

    def test_optional_requirements_use_dotted_edges(self, requirements,
                                                    salted_edges):
        """Extras are drawn as optional, required deps as solid"""
        for name, spec in requirements.items():
            _constraint, dotted = salted_edges[name]
            assert dotted == spec['optional'], (
                f'{name} is '
                f'{"an extra" if spec["optional"] else "required"} '
                f'but its edge is {"dotted" if dotted else "solid"}')


class TestGraphInternalConsistency:
    """Styling must follow from what a default install actually pulls in"""

    def test_only_solid_reachable_nodes_are_unmarked(self, nodes, edges):
        """Anything not reachable via solid edges must be :::optional.

        This is what catches a transitive dependency of an extra being
        left unmarked: latexcodec and PyYAML arrive only with pybtex, so
        they must be greyed out even though nothing about them changed.
        """
        solid = {}
        for src, dst, _constraint, dotted in edges:
            if not dotted:
                solid.setdefault(src, []).append(dst)

        reachable = set()
        queue = ['salted']
        while queue:
            current = queue.pop()
            for target in solid.get(current, []):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)

        for name, spec in nodes.items():
            if name == 'salted':
                continue
            if name in reachable:
                assert not spec['optional'], (
                    f'{name} is installed by default but marked optional')
            else:
                assert spec['optional'], (
                    f'{name} only arrives with an extra but is not '
                    'marked optional')

    def test_every_edge_endpoint_has_a_node(self, nodes, edges):
        """An edge must not point at an undeclared node"""
        for src, dst, _constraint, _dotted in edges:
            assert src in nodes, f'edge from undeclared node {src}'
            assert dst in nodes, f'edge to undeclared node {dst}'


class TestGraphDocumentSplit:
    """The prose and the generated graph must stay in separate files.

    scripts/generate_dependency_graph.py overwrites the diagram file whole.
    While the two lived together, every run deleted the hand-written notes -
    which is why they were split. These tests keep them apart.
    """

    def test_the_prose_file_holds_no_mermaid_block(self):
        """Anything put back here would be lost on the next regeneration."""
        assert '```mermaid' not in GRAPH_PROSE.read_text(encoding='utf-8'), (
            f'{GRAPH_PROSE.name} contains a mermaid block; it belongs in '
            f'{GRAPH.name}, which the generator overwrites')

    def test_the_prose_file_links_to_the_diagram(self):
        """The graph has to stay reachable from the document about it."""
        assert GRAPH.name in GRAPH_PROSE.read_text(encoding='utf-8'), (
            f'{GRAPH_PROSE.name} no longer links to {GRAPH.name}')

    def test_the_diagram_file_is_marked_as_generated(self, graph_text):
        """A reader opening it must see not to edit it by hand."""
        assert 'generate_dependency_graph.py' in graph_text

    def test_the_diagram_file_carries_only_the_graph(self, graph_text):
        """No prose may accumulate here: the generator would delete it."""
        outside = graph_text.split('```')[0]
        prose = [ln for ln in outside.splitlines()
                 if ln.strip() and not ln.strip().startswith('<!--')]
        assert not prose, f'unnamed prose above the graph: {prose}'
