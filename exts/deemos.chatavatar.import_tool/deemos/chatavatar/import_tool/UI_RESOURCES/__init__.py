import os

__FIXED_ELEMENTS = ["Background", "Title", "Confirm", "Import", "Back"]
__SELECTION_BUTTONS = ["DEFAULT", "METAHUMAN", "FOURK", "TWOK", "BLEND", "EYE", "RIGGED", "TEX"]

__FIXED_ELEMENTS_RELATIVE_PATHS = {
    # Fixed elements
    "Background": "Background_1.png",
    "Title": "ChatAvatar.png",
    "Confirm": "Confirm.png",
    "Import": "Import.png",
    "Back": "Back.png",
}

FIXED_ELEMENTS_ABSOLUTE_PATHS = {
    key: os.path.join(os.path.dirname(__file__), value)
    for key, value in __FIXED_ELEMENTS_RELATIVE_PATHS.items()
}

__SELECTION_BUTTONS_PATHS = {}

for i in __SELECTION_BUTTONS:
    __SELECTION_BUTTONS_PATHS[i] = {}
    for j in ["AVAILABLE", "UNAVAILABLE", "SELECTED"]:
        __SELECTION_BUTTONS_PATHS[i][j] = f"{i}_{j}.png"

SELECTION_BUTTONS_ABSOLUTE_PATHS = {
    key_1: {
        key_2: os.path.join(os.path.dirname(__file__), value_2)
        for key_2, value_2 in value_1.items()
    }
    for key_1, value_1 in __SELECTION_BUTTONS_PATHS.items()
}


def _assert_complete_pack():
    for i in __FIXED_ELEMENTS:
        assert i in FIXED_ELEMENTS_ABSOLUTE_PATHS, i
    for file_path in FIXED_ELEMENTS_ABSOLUTE_PATHS.values():
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        
    for i in __SELECTION_BUTTONS:
        assert i in SELECTION_BUTTONS_ABSOLUTE_PATHS, i
    for d in SELECTION_BUTTONS_ABSOLUTE_PATHS.values():
        for file_path in d.values():
            if not os.path.exists(file_path):
                raise FileNotFoundError(file_path)


_assert_complete_pack()
