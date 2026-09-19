from database.media_db import (
    MEDIA_CATEGORIES,
    MEDIA_TYPES,
    SOURCE_TYPES,
    add_media,
    delete_media,
    get_media_items,
    search_media,
    set_media_status,
    update_media,
)
from utils.display import print_footer, print_header, print_success, print_error, press_enter
from utils.validators import validate_menu_choice, validate_non_empty


def _read_optional_int(prompt, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            print_error("Enter a valid whole number or leave blank.")
            continue
        if value < 1:
            print_error("Enter a number greater than 0 or leave blank.")
            continue
        return value


def _read_yes_no(prompt, default=True):
    while True:
        raw = input(prompt).strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes", "1"):
            return True
        if raw in ("n", "no", "0"):
            return False
        print_error("Enter Y or N.")


def _choose(label, choices, current=None):
    print(f"\n{label}")
    for index, value in enumerate(choices, 1):
        suffix = " (Current)" if value == current else ""
        print(f"{index}. {value}{suffix}")
    selected = validate_menu_choice(
        "Select Choice : ",
        [str(i) for i in range(1, len(choices) + 1)]
    )
    return choices[int(selected) - 1]


def _display_media(row):
    print("-" * 80)
    print("Media ID         :", row["media_id"])
    print("Category         :", row["category"])
    print("Media Type       :", row["media_type"])
    print("Title            :", row["title"])
    print("Description      :", row["description"] or "-")
    print("Reference        :", row["media_reference"])
    print("Source Type      :", row["source_type"])
    print("Alt Text         :", row["alt_text"] or "-")
    print("Display Order    :", row["display_order"])
    print("Guest Visible    :", "Yes" if row["is_guest_visible"] else "No")
    print("Status           :", "Active" if row["is_active"] else "Inactive")
    print("Created          :", row["created_at"])
    print("Updated          :", row["updated_at"])


def _view_media():
    print_header("MEDIA GALLERY")
    rows = get_media_items()
    if not rows:
        print("No media records found.")
        print_footer()
        return
    for row in rows:
        _display_media(row)
    print_footer()


def _add_media():
    print_header("ADD HOTEL MEDIA")
    category = _choose("Category", MEDIA_CATEGORIES)
    media_type = _choose("Media Type", MEDIA_TYPES)
    title = validate_non_empty("Title : ")
    description = input("Description (Optional) : ").strip()
    media_reference = validate_non_empty(
        "Media Reference (file path or URL) : "
    )
    source_type = _choose("Source Type", SOURCE_TYPES, "Local File")
    alt_text = input("Alt Text (Optional) : ").strip()
    display_order = _read_optional_int("Display Order (Optional, default 1) : ", 1)
    guest_visible = _read_yes_no("Guest Visible? (Y/N, default Y) : ", True)

    media_id = add_media(
        category, media_type, title, description,
        media_reference, source_type, alt_text,
        display_order, guest_visible,
    )
    print_success(f"Media added successfully. Media ID: {media_id}")
    print_footer()


def _search_media():
    print_header("SEARCH MEDIA")
    search_text = input("Search Text : ").strip()
    category = None
    use_category = _read_yes_no("Filter by category? (Y/N, default N) : ", False)
    if use_category:
        category = _choose("Category", MEDIA_CATEGORIES)

    rows = search_media(search_text, category)
    if not rows:
        print("No matching media found.")
        print_footer()
        return
    for row in rows:
        _display_media(row)
    print_footer()


def _change_status():
    print_header("ACTIVATE / DEACTIVATE MEDIA")
    media_id = validate_non_empty("Media ID : ")
    print("1. Active")
    print("2. Inactive")
    choice = validate_menu_choice("Select Status : ", ["1", "2"])
    set_media_status(media_id, choice == "1")
    print_success("Media status updated successfully.")
    print_footer()


def _update_media():
    print_header("UPDATE MEDIA")
    media_id = validate_non_empty("Media ID : ")
    rows = get_media_items()
    current = next((row for row in rows if row["media_id"] == media_id), None)
    if current is None:
        raise ValueError("Media record not found.")

    category = _choose("Category", MEDIA_CATEGORIES, current["category"])
    media_type = _choose("Media Type", MEDIA_TYPES, current["media_type"])
    title = input(f"Title (Current: {current['title']}) : ").strip() or current["title"]
    description = input(
        f"Description (Current: {current['description'] or '-'}) : "
    ).strip() or (current["description"] or "")
    reference = input(
        f"Media Reference (Current: {current['media_reference']}) : "
    ).strip() or current["media_reference"]
    source_type = _choose("Source Type", SOURCE_TYPES, current["source_type"])
    alt_text = input(
        f"Alt Text (Current: {current['alt_text'] or '-'}) : "
    ).strip() or (current["alt_text"] or "")
    display_order = _read_optional_int(
        f"Display Order (Current: {current['display_order']}) : ",
        current["display_order"],
    )
    guest_visible = _read_yes_no(
        f"Guest Visible? (Y/N, current {'Y' if current['is_guest_visible'] else 'N'}) : ",
        bool(current["is_guest_visible"]),
    )

    update_media(
        media_id, category, media_type, title, description,
        reference, source_type, alt_text, display_order, guest_visible,
    )
    print_success("Media updated successfully.")
    print_footer()


def _delete_media():
    print_header("REMOVE MEDIA")
    media_id = validate_non_empty("Media ID : ")
    confirm = _read_yes_no(
        "Remove this media database reference? Physical file will not be deleted. (Y/N) : ",
        False,
    )
    if not confirm:
        print("Operation cancelled.")
        print_footer()
        return
    delete_media(media_id)
    print_success("Media reference removed successfully.")
    print_footer()


def media_management():
    while True:
        print_header("HOTEL VISUAL / MEDIA SYSTEM")
        print("1. Media Gallery")
        print("2. Add Media")
        print("3. Search Media")
        print("4. Update Media")
        print("5. Activate / Deactivate Media")
        print("6. Remove Media Reference")
        print("7. Back")
        print_footer()

        choice = validate_menu_choice(
            "Enter Choice : ",
            ["1", "2", "3", "4", "5", "6", "7"],
        )
        try:
            if choice == "1":
                _view_media()
            elif choice == "2":
                _add_media()
            elif choice == "3":
                _search_media()
            elif choice == "4":
                _update_media()
            elif choice == "5":
                _change_status()
            elif choice == "6":
                _delete_media()
            else:
                break
        except ValueError as error:
            print_error(str(error))

        if choice != "7":
            press_enter()
