#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol


# =============================================================================
# Logging
# =============================================================================


def progress(message: str) -> None:
    print(message, file=sys.stderr)


# =============================================================================
# Arguments / config
# =============================================================================


@dataclass(frozen=True)
class Config:
    source_json: str
    output: str = "txt"
    show_schema: bool = False
    search_keys: tuple[str, ...] = ()
    search_vals: tuple[str, ...] = ()
    include_search_children: bool = False
    hide_fields_matching: tuple[str, ...] = ()
    hide_fields_containing: tuple[str, ...] = ()
    truncate_line_length: int | None = None
    show_line_numbers: bool = True
    indent_size: int = 2


class CliError(Exception):
    pass


class ArgValidator:
    def validate(self, config: Config) -> None:
        self._validate_schema_mode(config)

    def _validate_schema_mode(self, config: Config) -> None:
        if not config.show_schema:
            return

        incompatible = [
            config.output != "txt",
            bool(config.search_keys),
            bool(config.search_vals),
            config.include_search_children,
            bool(config.hide_fields_matching),
            bool(config.hide_fields_containing),
            config.truncate_line_length is not None,
            not config.show_line_numbers,
            config.indent_size != 2,
        ]
        if any(incompatible):
            raise CliError("--show-schema not compatible with other arguments")


def normalize_terms(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(v.casefold() for v in values)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read JSON as a stripped indentation-based tree, CSV, JSON, or schema."
    )
    parser.add_argument("source_json", help="Path to source JSON file")
    parser.add_argument("--output", choices=["txt", "csv", "json"], default="txt")
    parser.add_argument("--show-schema", action="store_true")
    parser.add_argument("--search-keys", nargs="+", default=[])
    parser.add_argument("--search-vals", nargs="+", default=[])
    parser.add_argument("--include-search-children", action="store_true")
    parser.add_argument("--hide-fields-matching", nargs="+", default=[])
    parser.add_argument("--hide-fields-containing", nargs="+", default=[])
    parser.add_argument("--truncate-line-length", type=int, default=None)
    parser.add_argument("--hide-line-numbers", action="store_true")
    parser.add_argument("--indent-size", type=int, default=2)
    return parser


def parse_config(argv: list[str] | None = None) -> Config:
    args = build_parser().parse_args(argv)
    config = Config(
        source_json=args.source_json,
        output=args.output,
        show_schema=args.show_schema,
        search_keys=normalize_terms(args.search_keys),
        search_vals=normalize_terms(args.search_vals),
        include_search_children=args.include_search_children,
        hide_fields_matching=tuple(args.hide_fields_matching),
        hide_fields_containing=normalize_terms(args.hide_fields_containing),
        truncate_line_length=args.truncate_line_length,
        show_line_numbers=not args.hide_line_numbers,
        indent_size=args.indent_size,
    )
    ArgValidator().validate(config)
    return config


# =============================================================================
# Neutral document tree
# =============================================================================


@dataclass
class HiddenSummary:
    hidden_count: int


@dataclass
class Node:
    label: str | None
    value_text: str | None = None
    children: list[Node] = field(default_factory=list)
    hidden_summary: HiddenSummary | None = None

    def has_content(self) -> bool:
        return bool(self.value_text is not None or self.children or self.hidden_summary)


@dataclass(frozen=True)
class SearchInfo:
    relevant: bool
    direct_match: bool
    hit_count: int


# =============================================================================
# Helpers
# =============================================================================


class JsonValueTools:
    @staticmethod
    def is_scalar(value: Any) -> bool:
        return not isinstance(value, (dict, list))

    @staticmethod
    def scalar_to_text(value: Any) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)


class MatchRules:
    def __init__(self, config: Config):
        self._config = config

    def search_active(self) -> bool:
        return bool(self._config.search_keys or self._config.search_vals)

    def key_matches(self, key: str) -> bool:
        key_folded = key.casefold()
        return any(term in key_folded for term in self._config.search_keys)

    def value_matches(self, value: Any) -> bool:
        if not JsonValueTools.is_scalar(value):
            return False
        text = JsonValueTools.scalar_to_text(value).casefold()
        return any(term in text for term in self._config.search_vals)

    def hide_key(self, key: str) -> bool:
        exact_match = key in self._config.hide_fields_matching
        contains_match = any(term in key.casefold() for term in self._config.hide_fields_containing)
        return exact_match or contains_match


class HiddenCounter:
    @staticmethod
    def count(value: Any) -> int:
        if JsonValueTools.is_scalar(value):
            return 1
        if isinstance(value, dict):
            return 1 if not value else sum(HiddenCounter.count(v) for v in value.values())
        if isinstance(value, list):
            return 1 if not value else sum(HiddenCounter.count(v) for v in value)
        return 1


# =============================================================================
# Pipeline protocol and context
# =============================================================================


@dataclass
class PipelineContext:
    config: Config
    raw_json: Any = None
    search_info: SearchInfo | None = None
    tree: Node | None = None
    output_text: str = ""


class Stage(Protocol):
    def run(self, context: PipelineContext) -> PipelineContext:
        ...


# =============================================================================
# Stage 1: Parse
# =============================================================================


class ParseJsonStage:
    def run(self, context: PipelineContext) -> PipelineContext:
        progress("performing parse...")
        with open(context.config.source_json, "r", encoding="utf-8") as handle:
            context.raw_json = json.load(handle)
        progress("parse complete: 1 file loaded")
        return context


# =============================================================================
# Search analysis service
# =============================================================================


class SearchAnalyzer:
    def __init__(self, config: Config):
        self._rules = MatchRules(config)

    def analyze(self, value: Any, label: str | None = None) -> SearchInfo:
        if not self._rules.search_active():
            return SearchInfo(relevant=True, direct_match=True, hit_count=0)

        own_match = self._direct_match(label, value)
        child_hit_count, child_relevant = self._child_results(value)
        hit_count = int(own_match) + child_hit_count
        return SearchInfo(
            relevant=own_match or child_relevant,
            direct_match=own_match,
            hit_count=hit_count,
        )

    def _direct_match(self, label: str | None, value: Any) -> bool:
        key_hit = bool(label is not None and self._rules.key_matches(label))
        value_hit = self._rules.value_matches(value)
        return key_hit or value_hit

    def _child_results(self, value: Any) -> tuple[int, bool]:
        if isinstance(value, dict):
            infos = [self.analyze(child_value, child_key) for child_key, child_value in value.items()]
            return sum(info.hit_count for info in infos), any(info.relevant for info in infos)
        if isinstance(value, list):
            infos = [self.analyze(item, None) for item in value]
            return sum(info.hit_count for info in infos), any(info.relevant for info in infos)
        return 0, False


# =============================================================================
# Stage 2: Search report
# =============================================================================


class SearchReportStage:
    def run(self, context: PipelineContext) -> PipelineContext:
        progress("performing search analysis...")
        analyzer = SearchAnalyzer(context.config)
        context.search_info = analyzer.analyze(context.raw_json)
        if analyzer._rules.search_active():
            progress(f"search analysis complete: {context.search_info.hit_count} hit(s) found")
        else:
            progress("search analysis complete: full document mode")
        return context


# =============================================================================
# Tree build services
# =============================================================================


class IncludeDecision:
    def __init__(self, config: Config, analyzer: SearchAnalyzer):
        self._config = config
        self._analyzer = analyzer
        self._rules = MatchRules(config)

    def include_all_visible_descendants(self, parent_info: SearchInfo) -> bool:
        if not self._rules.search_active():
            return True
        return parent_info.direct_match and self._config.include_search_children

    def include_child(self, parent_info: SearchInfo, child_value: Any, child_label: str | None) -> bool:
        if self.include_all_visible_descendants(parent_info):
            return True
        if not self._rules.search_active():
            return True
        return self._analyzer.analyze(child_value, child_label).relevant


class NodeBuilder:
    def __init__(self, config: Config):
        self._config = config
        self._rules = MatchRules(config)
        self._analyzer = SearchAnalyzer(config)
        self._include_decision = IncludeDecision(config, self._analyzer)

    def build(self, value: Any, label: str | None = None) -> Node | None:
        info = self._analyzer.analyze(value, label)
        return self._build_node(value, label, info)

    def _build_node(self, value: Any, label: str | None, info: SearchInfo) -> Node | None:
        relevance_gate = info.relevant
        if not relevance_gate:
            return None

        hidden_gate = bool(label is not None and self._rules.hide_key(label))
        if hidden_gate:
            return self._build_hidden_summary(label, value)

        scalar_gate = JsonValueTools.is_scalar(value)
        if scalar_gate:
            return self._build_scalar(label, value)

        return self._build_container(label, value, info)

    def _build_hidden_summary(self, label: str, value: Any) -> Node:
        scalar_gate = JsonValueTools.is_scalar(value)
        if scalar_gate:
            return Node(label=label, value_text="[hidden]")
        return Node(
            label=label,
            children=[Node(label=f"[{HiddenCounter.count(value)} hidden]")],
        )

    def _build_scalar(self, label: str | None, value: Any) -> Node:
        text = JsonValueTools.scalar_to_text(value)
        if label is None:
            return Node(label=text)
        return Node(label=label, value_text=text)

    def _build_container(self, label: str | None, value: Any, info: SearchInfo) -> Node | None:
        children = self._build_children(value, info)
        node = Node(label=label, children=children)
        root_gate = label is None
        container_with_children_gate = bool(children)
        if root_gate and container_with_children_gate:
            return node
        if container_with_children_gate:
            return node
        direct_match_gate = info.direct_match
        if direct_match_gate:
            return Node(label=label)
        return None

    def _build_children(self, value: Any, info: SearchInfo) -> list[Node]:
        if isinstance(value, dict):
            return self._build_object_children(value, info)
        if isinstance(value, list):
            return self._build_list_children(value, info)
        return []

    def _build_object_children(self, value: dict[str, Any], info: SearchInfo) -> list[Node]:
        items = ((child_key, child_value) for child_key, child_value in value.items())
        return self._collect_child_nodes(items, info)

    def _build_list_children(self, value: list[Any], info: SearchInfo) -> list[Node]:
        items = ((f"[{index}]", child_value) for index, child_value in enumerate(value))
        return self._collect_child_nodes(items, info)

    def _collect_child_nodes(self, items: Iterable[tuple[str, Any]], info: SearchInfo) -> list[Node]:
        nodes: list[Node] = []
        include_all_visible_descendants = self._include_decision.include_all_visible_descendants(info)
        for child_label, child_value in items:
            include_gate = self._include_decision.include_child(info, child_value, child_label)
            if not include_gate:
                continue
            child_node = (
                self._build_visible_subtree(child_value, child_label)
                if include_all_visible_descendants
                else self._build_node(child_value, child_label, self._analyzer.analyze(child_value, child_label))
            )
            content_gate = bool(child_node is not None and child_node.has_content())
            if not content_gate:
                continue
            nodes.append(child_node)
        return nodes

    def _build_visible_subtree(self, value: Any, label: str | None) -> Node | None:
        hidden_gate = bool(label is not None and self._rules.hide_key(label))
        if hidden_gate:
            return self._build_hidden_summary(label, value)
        scalar_gate = JsonValueTools.is_scalar(value)
        if scalar_gate:
            return self._build_scalar(label, value)
        children = self._build_visible_children(value)
        root_gate = label is None
        if root_gate:
            return Node(label=label, children=children) if children else None
        return Node(label=label, children=children) if children else Node(label=label)

    def _build_visible_children(self, value: Any) -> list[Node]:
        if isinstance(value, dict):
            items = ((child_key, child_value) for child_key, child_value in value.items())
            return self._collect_visible_child_nodes(items)
        if isinstance(value, list):
            items = ((f"[{index}]", child_value) for index, child_value in enumerate(value))
            return self._collect_visible_child_nodes(items)
        return []

    def _collect_visible_child_nodes(self, items: Iterable[tuple[str, Any]]) -> list[Node]:
        nodes: list[Node] = []
        for child_label, child_value in items:
            child_node = self._build_visible_subtree(child_value, child_label)
            if child_node is None or not child_node.has_content():
                continue
            nodes.append(child_node)
        return nodes


# =============================================================================
# Stage 3: Build tree
# =============================================================================


class BuildTreeStage:
    def run(self, context: PipelineContext) -> PipelineContext:
        progress("performing tree build...")
        builder = NodeBuilder(context.config)
        context.tree = builder.build(context.raw_json)
        top_level_count = 0 if context.tree is None else len(context.tree.children)
        progress(f"tree build complete: {top_level_count} top-level node(s)")
        return context


# =============================================================================
# Render models
# =============================================================================


class Renderer(Protocol):
    def render(self, context: PipelineContext) -> str:
        ...


class TextRenderModel:
    def __init__(self, config: Config):
        self._config = config

    def build_lines(self, tree: Node | None) -> list[str]:
        if tree is None:
            return ["<no matches>"]
        lines: list[str] = []
        self._walk(tree, 0, lines)
        return lines or ["<no matches>"]

    def _walk(self, node: Node, depth: int, lines: list[str]) -> None:
        label_gate = bool(node.label not in (None, ""))
        if label_gate:
            lines.append(self._format_line(node, depth))
        next_depth = depth if node.label in (None, "") else depth + 1
        for child in node.children:
            self._walk(child, next_depth, lines)

    def _format_line(self, node: Node, depth: int) -> str:
        indent = " " * (depth * self._config.indent_size)
        value_gate = bool(node.value_text is not None)
        if value_gate:
            return f"{indent}{node.label}: {node.value_text}"
        return f"{indent}{node.label}"


class LineFormatter:
    def __init__(self, config: Config):
        self._config = config

    def apply_text_line_rules(self, lines: list[str]) -> list[str]:
        lines = self._truncate_lines(lines)
        return self._add_line_numbers(lines) if self._config.show_line_numbers else lines

    def _truncate_lines(self, lines: list[str]) -> list[str]:
        max_len = self._config.truncate_line_length
        if max_len is None:
            return lines
        return [self._truncate_text(line, max_len) for line in lines]

    def _add_line_numbers(self, lines: list[str]) -> list[str]:
        width = len(str(len(lines)))
        return [f"{index:>{width}} | {line}" for index, line in enumerate(lines, 1)]

    @staticmethod
    def _truncate_text(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        if max_len <= 0:
            return ""
        if max_len == 1:
            return "…"
        return text[: max_len - 1] + "…"


class TextRenderer:
    def render(self, context: PipelineContext) -> str:
        model = TextRenderModel(context.config)
        lines = model.build_lines(context.tree)
        return "\n".join(LineFormatter(context.config).apply_text_line_rules(lines))


class JsonProjectionBuilder:
    def build(self, tree: Node | None) -> Any:
        if tree is None:
            return None
        if tree.label in (None, ""):
            return self._root_projection(tree)
        return self._node_projection(tree)

    def _root_projection(self, root: Node) -> Any:
        if not root.children:
            return None
        return {child.label: self._node_payload(child) for child in root.children}

    def _node_projection(self, node: Node) -> Any:
        return {node.label: self._node_payload(node)}

    def _node_payload(self, node: Node) -> Any:
        scalar_gate = bool(node.value_text is not None)
        if scalar_gate:
            return node.value_text
        leaf_gate = not node.children
        if leaf_gate:
            return None
        array_gate = self._children_are_arrayish(node.children)
        if array_gate:
            return [self._node_payload(child) for child in node.children]
        return {child.label: self._node_payload(child) for child in node.children}

    @staticmethod
    def _children_are_arrayish(children: list[Node]) -> bool:
        return bool(children) and all((child.label or "").startswith("[") for child in children)


class JsonRenderer:
    def render(self, context: PipelineContext) -> str:
        projection = JsonProjectionBuilder().build(context.tree)
        return json.dumps(projection, indent=2, ensure_ascii=False)


class CsvPathCollector:
    def collect(self, tree: Node | None) -> list[list[str]]:
        if tree is None:
            return []
        rows: list[list[str]] = []
        self._walk(tree, [], rows)
        return rows

    def _walk(self, node: Node, path: list[str], rows: list[list[str]]) -> None:
        current_path = path if node.label in (None, "") else path + [node.label]
        scalar_gate = bool(node.value_text is not None)
        if scalar_gate:
            rows.append(current_path + [node.value_text])
            return
        leaf_gate = bool(node.label not in (None, "") and not node.children)
        if leaf_gate:
            rows.append(current_path)
            return
        for child in node.children:
            self._walk(child, current_path, rows)


class CsvRenderer:
    def render(self, context: PipelineContext) -> str:
        rows = CsvPathCollector().collect(context.tree)
        rendered_rows = self._apply_truncation(rows, context.config.truncate_line_length)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        if context.config.show_line_numbers:
            for index, row in enumerate(rendered_rows, 1):
                writer.writerow([index] + row)
        else:
            writer.writerows(rendered_rows)
        return buffer.getvalue().rstrip("\n")

    def _apply_truncation(self, rows: list[list[str]], max_len: int | None) -> list[list[str]]:
        if max_len is None:
            return rows
        return [[self._truncate_cell(cell, max_len) for cell in row] for row in rows]

    @staticmethod
    def _truncate_cell(cell: str, max_len: int) -> str:
        if len(cell) <= max_len:
            return cell
        if max_len <= 0:
            return ""
        if max_len == 1:
            return "…"
        return cell[: max_len - 1] + "…"


class SchemaExplorer:
    def build_schema(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self.build_schema(child) for key, child in value.items()}
        if isinstance(value, list):
            sample = self.build_schema(value[0]) if value else "empty-array"
            return [sample]
        return type(value).__name__


class SchemaRenderer:
    def render(self, context: PipelineContext) -> str:
        schema = SchemaExplorer().build_schema(context.raw_json)
        return json.dumps(schema, indent=2, ensure_ascii=False)


class RendererFactory:
    def create(self, config: Config) -> Renderer:
        if config.show_schema:
            return SchemaRenderer()
        if config.output == "json":
            return JsonRenderer()
        if config.output == "csv":
            return CsvRenderer()
        return TextRenderer()


# =============================================================================
# Stage 4: Render
# =============================================================================


class RenderStage:
    def run(self, context: PipelineContext) -> PipelineContext:
        progress("performing render...")
        context.output_text = RendererFactory().create(context.config).render(context)
        line_count = 0 if not context.output_text else len(context.output_text.splitlines())
        progress(f"render complete: {line_count} line(s) produced")
        return context


# =============================================================================
# Pipeline + entrypoint
# =============================================================================


class Pipeline:
    def __init__(self, stages: list[Stage]):
        self._stages = stages

    def run(self, context: PipelineContext) -> PipelineContext:
        for stage in self._stages:
            context = stage.run(context)
        return context


def default_pipeline() -> Pipeline:
    return Pipeline([
        ParseJsonStage(),
        SearchReportStage(),
        BuildTreeStage(),
        RenderStage(),
    ])


def run_cli(argv: list[str] | None = None) -> int:
    try:
        config = parse_config(argv)
        context = PipelineContext(config=config)
        context = default_pipeline().run(context)
        print(context.output_text)
        return 0
    except CliError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"file not found: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
