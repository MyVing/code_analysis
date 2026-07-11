import logging
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

logger = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(tsjava.language())


class TreeSitterParser:
    def __init__(self):
        self.parser = Parser(JAVA_LANGUAGE)

    def parse_file(self, file_path: Path) -> Node | None:
        source = file_path.read_bytes()
        tree = self.parser.parse(source)
        return tree.root_node

    def parse_source(self, source: str | bytes) -> Node | None:
        if isinstance(source, str):
            source = source.encode("utf-8")
        tree = self.parser.parse(source)
        return tree.root_node
