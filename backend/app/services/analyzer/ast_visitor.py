import logging
from dataclasses import dataclass, field

from tree_sitter import Node

from app.models.symbol import SymbolKind

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    name: str
    kind: SymbolKind
    start_line: int
    end_line: int
    signature: str | None = None
    modifiers: str | None = None
    parent_name: str | None = None
    children: list["SymbolInfo"] = field(default_factory=list)


@dataclass
class CallInfo:
    caller_name: str
    callee_name: str
    line_number: int
    file_path: str | None = None


@dataclass
class FieldAccessInfo:
    accessor_name: str
    field_name: str
    line_number: int
    file_path: str | None = None


@dataclass
class ImportInfo:
    module_path: str
    import_type: str
    line_number: int


@dataclass
class ImplementsInfo:
    class_name: str
    interface_names: list[str]


class JavaASTVisitor:
    def __init__(self):
        self.symbols: list[SymbolInfo] = []
        self.calls: list[CallInfo] = []
        self.field_accesses: list[FieldAccessInfo] = []
        self.imports: list[ImportInfo] = []
        self.implements_list: list[ImplementsInfo] = []
        self._current_class: str | None = None

    def visit(self, node: Node) -> None:
        if node.type == "class_declaration":
            self._visit_class(node)
        elif node.type == "interface_declaration":
            self._visit_interface(node)
        elif node.type == "enum_declaration":
            self._visit_enum(node)
        elif node.type == "import_declaration":
            self._visit_import(node)
        elif node.type == "method_declaration":
            self._visit_method(node)
        else:
            for child in node.children:
                self.visit(child)

    def _visit_class(self, node: Node) -> None:
        name = self._get_identifier(node)
        modifiers = self._get_modifiers(node)
        symbol = SymbolInfo(
            name=name,
            kind=SymbolKind.CLASS,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            modifiers=modifiers,
        )
        # Extract implements clause
        interface_names = self._get_implements_names(node)
        if interface_names:
            self.implements_list.append(ImplementsInfo(
                class_name=name,
                interface_names=interface_names,
            ))
        prev_class = self._current_class
        self._current_class = name
        for child in node.children:
            if child.type == "class_body":
                self._visit_class_body(child, symbol)
        self._current_class = prev_class
        self.symbols.append(symbol)

    def _visit_interface(self, node: Node) -> None:
        name = self._get_identifier(node)
        modifiers = self._get_modifiers(node)
        symbol = SymbolInfo(
            name=name,
            kind=SymbolKind.INTERFACE,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            modifiers=modifiers,
        )
        prev_class = self._current_class
        self._current_class = name
        for child in node.children:
            if child.type == "interface_body":
                self._visit_interface_body(child, symbol)
        self._current_class = prev_class
        self.symbols.append(symbol)

    def _visit_enum(self, node: Node) -> None:
        name = self._get_identifier(node)
        symbol = SymbolInfo(
            name=name,
            kind=SymbolKind.ENUM,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
        self.symbols.append(symbol)

    def _visit_class_body(self, node: Node, parent: SymbolInfo) -> None:
        for child in node.children:
            if child.type == "method_declaration":
                method = self._visit_method(child)
                if method:
                    method.parent_name = parent.name
                    parent.children.append(method)
            elif child.type == "field_declaration":
                self._visit_field(child, parent)
            elif child.type == "class_declaration":
                self._visit_class(child)
            elif child.type == "constructor_declaration":
                method = self._visit_constructor(child)
                if method:
                    method.parent_name = parent.name
                    parent.children.append(method)

    def _visit_interface_body(self, node: Node, parent: SymbolInfo) -> None:
        for child in node.children:
            if child.type == "method_declaration":
                method = self._visit_method(child)
                if method:
                    method.parent_name = parent.name
                    parent.children.append(method)

    def _visit_method(self, node: Node) -> SymbolInfo | None:
        name = self._get_method_name(node)
        if not name:
            return None
        modifiers = self._get_modifiers(node)
        signature = self._get_method_signature(node)
        caller_qualified = f"{self._current_class}.{name}" if self._current_class else name
        symbol = SymbolInfo(
            name=name,
            kind=SymbolKind.METHOD,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            modifiers=modifiers,
        )
        self._collect_calls(node, caller_qualified)
        return symbol

    def _visit_constructor(self, node: Node) -> SymbolInfo | None:
        name = self._get_method_name(node)
        if not name:
            return None
        caller_qualified = f"{self._current_class}.<init>" if self._current_class else "<init>"
        symbol = SymbolInfo(
            name=f"<init>",
            kind=SymbolKind.METHOD,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=name + "()",
            modifiers=self._get_modifiers(node),
        )
        self._collect_calls(node, caller_qualified)
        return symbol

    def _visit_field(self, node: Node, parent: SymbolInfo) -> None:
        for child in node.children:
            if child.type == "variable_declarator":
                var_name = child.child_by_field_name("name")
                if var_name:
                    symbol = SymbolInfo(
                        name=var_name.text.decode("utf-8"),
                        kind=SymbolKind.VARIABLE,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent_name=parent.name,
                        modifiers=self._get_modifiers(node),
                    )
                    parent.children.append(symbol)

    def _visit_import(self, node: Node) -> None:
        is_static = False
        is_wildcard = False
        module_parts = []
        for child in node.children:
            if child.type == "static":
                is_static = True
            elif child.type == "asterisk":
                is_wildcard = True
            elif child.type == "scoped_identifier" or child.type == "identifier":
                module_parts.append(child.text.decode("utf-8"))

        module_path = ".".join(module_parts) if module_parts else ""
        if is_wildcard:
            module_path += ".*"

        import_type = "static_import" if is_static else "import"
        self.imports.append(ImportInfo(
            module_path=module_path,
            import_type=import_type,
            line_number=node.start_point[0] + 1,
        ))

    def _collect_calls(self, node: Node, caller_name: str) -> None:
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == "method_invocation":
                callee = self._get_call_name(current)
                if callee:
                    self.calls.append(CallInfo(
                        caller_name=caller_name,
                        callee_name=callee,
                        line_number=current.start_point[0] + 1,
                    ))
                # Also record field access: obj.method() -> access to obj field
                field_name = self._get_field_access_from_invocation(current)
                if field_name:
                    self.field_accesses.append(FieldAccessInfo(
                        accessor_name=caller_name,
                        field_name=field_name,
                        line_number=current.start_point[0] + 1,
                    ))
            elif current.type == "field_access":
                # Direct field access: this.fieldName or obj.fieldName
                fa_name = self._get_field_access_name(current)
                if fa_name:
                    self.field_accesses.append(FieldAccessInfo(
                        accessor_name=caller_name,
                        field_name=fa_name,
                        line_number=current.start_point[0] + 1,
                    ))
            for child in current.children:
                if child.type not in ("method_declaration", "class_declaration"):
                    stack.append(child)

    def _get_identifier(self, node: Node) -> str:
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
        return ""

    def _get_implements_names(self, node: Node) -> list[str]:
        """Extract interface names from the implements clause of a class declaration."""
        for child in node.children:
            if child.type == "super_interfaces":
                names = []
                for si_child in child.children:
                    if si_child.type == "type_list":
                        for type_child in si_child.children:
                            if type_child.type == "type_identifier":
                                names.append(type_child.text.decode("utf-8"))
                            elif type_child.type == "generic_type":
                                # e.g. Comparable<T> -> take the base type_identifier
                                for gc in type_child.children:
                                    if gc.type == "type_identifier":
                                        names.append(gc.text.decode("utf-8"))
                                        break
                return names
        return []

    def _get_method_name(self, node: Node) -> str | None:
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
        return None

    def _get_modifiers(self, node: Node) -> str | None:
        mods = []
        for child in node.children:
            if child.type in ("public", "private", "protected", "static",
                              "final", "abstract", "synchronized", "native"):
                mods.append(child.type)
        return " ".join(mods) if mods else None

    def _get_method_signature(self, node: Node) -> str | None:
        name = self._get_method_name(node)
        if not name:
            return None
        params = []
        for child in node.children:
            if child.type == "formal_parameters":
                for param in child.children:
                    if param.type == "formal_parameter":
                        parts = [c.text.decode("utf-8") for c in param.children if c.type in ("type_identifier", "generic_type", "array_type")]
                        if parts:
                            params.append(parts[0])
        return f"{name}({', '.join(params)})"

    def _get_call_name(self, node: Node) -> str | None:
        # Java method_invocation structure:
        #   object.method(args) -> [object_ref, ".", method_name, args]
        #   method(args)        -> [method_name, args]
        parts = []
        for child in node.children:
            if child.type == "identifier":
                parts.append(child.text.decode("utf-8"))
            elif child.type == "field_access":
                parts.append(child.text.decode("utf-8").replace(" ", ""))
            elif child.type == "scoped_identifier":
                parts.append(child.text.decode("utf-8").replace(" ", ""))
        if not parts:
            return None
        return ".".join(parts)

    def _get_field_access_from_invocation(self, node: Node) -> str | None:
        """Extract the object/field reference from a method invocation like obj.method().
        Returns 'ClassName.fieldName' or just 'fieldName'."""
        for child in node.children:
            if child.type == "field_access":
                return self._get_field_access_name(child)
            elif child.type == "identifier":
                # Check if this identifier is the object part (not the method name)
                # In method_invocation: [object, ".", method, args]
                pass
        # Try to extract object reference from the first parts
        parts = []
        for child in node.children:
            if child.type == "identifier":
                parts.append(child.text.decode("utf-8"))
            elif child.type == "field_access":
                return self._get_field_access_name(child)
        # If there are 2+ identifiers: first is object/field, rest is method
        if len(parts) >= 2:
            field_ref = parts[0]
            qualified = f"{self._current_class}.{field_ref}" if self._current_class else field_ref
            return qualified
        return None

    def _get_field_access_name(self, node: Node) -> str | None:
        """Extract field name from a field_access node like 'this.userMapper' or 'userMapper'."""
        parts = []
        for child in node.children:
            if child.type == "identifier":
                parts.append(child.text.decode("utf-8"))
            elif child.type == "this":
                pass  # skip 'this'
            elif child.type == ".":
                pass
        # Filter out 'this' and get the field name
        # e.g., this.userMapper -> ['userMapper']
        # e.g., userMapper -> ['userMapper']
        field_parts = [p for p in parts if p != "this"]
        if not field_parts:
            return None
        # The last part is the field name, preceding parts are the class/object
        if len(field_parts) >= 2:
            qualified = f"{field_parts[-2]}.{field_parts[-1]}"
            return qualified
        field_name = field_parts[0]
        qualified = f"{self._current_class}.{field_name}" if self._current_class else field_name
        return qualified
