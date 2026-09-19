"""AI-Ready Business Tools console foundation.

This is a development/admin surface for inspecting the tool contract. Actual
AI reasoning, external channels, and API transport remain future phases.
"""

import json

from database.ai_tools_db import (
    execute_ai_tool,
    get_tool_definition,
    get_tool_registry,
)


def _pause():
    input("\nPress Enter To Continue...")


def _print_registry():
    print("=" * 72)
    print("AI-READY BUSINESS TOOL REGISTRY")
    print("=" * 72)
    for index, tool in enumerate(get_tool_registry(), start=1):
        print(f"{index}. {tool['name']}")
        print(f"   Category       : {tool['category']}")
        print(f"   Read Only      : {'Yes' if tool['read_only'] else 'No'}")
        print(f"   Description    : {tool['description']}")
        required = ", ".join(tool["required_arguments"]) or "None"
        optional = ", ".join(tool["optional_arguments"]) or "None"
        print(f"   Required Args  : {required}")
        print(f"   Optional Args  : {optional}")
        print("-" * 72)


def _execute_tool():
    print("=" * 72)
    print("EXECUTE AI-READY BUSINESS TOOL")
    print("=" * 72)
    print("Enter a registered tool name. Example: hotel_information")
    tool_name = input("Tool Name : ").strip().lower()
    definition = get_tool_definition(tool_name)
    if definition is None:
        print("❌ Unknown tool name.")
        return

    print(f"Description : {definition['description']}")
    print(f"Read Only   : {'Yes' if definition['read_only'] else 'No'}")
    print("Arguments must be a JSON object. Leave blank for no arguments.")
    raw = input("Arguments JSON : ").strip()
    try:
        arguments = json.loads(raw) if raw else {}
        result = execute_ai_tool(tool_name, arguments)
        print("\n✅ Tool executed successfully.")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"❌ Tool execution failed: {exc}")


def ai_tools_management():
    while True:
        print("=" * 72)
        print("AI-READY BUSINESS TOOLS")
        print("=" * 72)
        print("1. Tool Registry")
        print("2. Execute AI Tool")
        print("3. Back")
        print("-" * 72)

        choice = input("Enter Choice : ").strip()

        if choice == "1":
            _print_registry()
            _pause()
        elif choice == "2":
            _execute_tool()
            _pause()
        elif choice == "3":
            return
        else:
            print("❌ Invalid Choice.")
