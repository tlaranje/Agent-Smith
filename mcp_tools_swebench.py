""" def dispatch_tool(self, tool_name: str | None, tool_args: dict) -> str:
        print("tool_name", tool_name)
        tools = {
            "read_file":       self._tool_read_file,
            "edit_file":       self._tool_edit_file,
            "list_files":      self._tool_list_files,
            "search_code":     self._tool_search_code,
            "search_function_or_class_definition_in_code": (
                self._tool_search_definition
            ),
            "find_references": self._tool_find_references,
            "run_tests":       self._tool_run_tests,
            "run_command":     self._tool_run_command,
            "final_answer": lambda _: "",
        }
        if tool_name not in tools:
            return f"ERROR: Unknown tool '{tool_name}'. Available: {', '.join(tools.keys())}"
        try:
            return tools[tool_name](tool_args)
        except KeyError as e:
            return f"ERROR: Missing required argument {e} for tool '{tool_name}'."
        except Exception as e:
            return f"ERROR: Tool '{tool_name}' failed: {e}"

    def _tool_read_file(self, args: dict) -> str:
        return self.sandbox.read_file(args["filepath"], args.get("start_line"), args.get("end_line"))

    def _tool_edit_file(self, args: dict) -> str:
        return self.sandbox.edit_file(args["filepath"], args["old_str"], args["new_str"])

    def _tool_list_files(self, args: dict) -> str:
        return self.sandbox.list_files(args["directory"], args.get("pattern", "*"))

    def _tool_search_code(self, args: dict) -> str:
        return self.sandbox.search_code(args["pattern"], args.get("file_pattern", "*.py"))

    def _tool_search_definition(self, args: dict) -> str:
        return self.sandbox.search_function_or_class_definition_in_code(args["name"])

    def _tool_find_references(self, args: dict) -> str:
        return self.sandbox.find_references(args["name"], args.get("filepath"), args.get("line"))

    def _tool_run_tests(self, args: dict) -> str:
        return self.sandbox.run_tests()

    def _tool_run_command(self, args: dict) -> str:
        return self.sandbox.run_command(args["command"], args.get("workdir", "/testbed"))
 """
