import json
from pathlib import Path

import aqt
from aqt import gui_hooks, mw
from aqt.editor import Editor

from .config import remove, set
from .user_config import getUserOption
from .utils import distinct

# limit for options sent to autocomplete.js at once
MAXIMUM_OPTION_AMOUNT = 20

mw.addonManager.setWebExports(__name__, r"(web|icons)/.*\.(js|css|png)")


def handle_bridge_commands(handled, cmd, context):
    if not isinstance(context, Editor):
        return handled

    editor: Editor = context

    if cmd.startswith("autocomplete"):
        if handle_autocomplete(cmd, editor):
            return (True, None)
    elif cmd.startswith("update_ac_settings"):
        if handle_update_ac_settings(cmd, editor):
            return (True, None)

    return handled


def handle_update_ac_settings(cmd, editor):
    (_, jsonText) = cmd.split(":", 1)
    data = json.loads(jsonText)
    ord, enabled = data.values()

    note_type = editor.note.note_type()
    fld = next(x for x in note_type['flds'] if x['ord'] == ord)
    id = f'{note_type["id"]} {fld["name"]}'
    if enabled:
        set(id, True)
    else:
        remove(id)

    return True


def handle_autocomplete(cmd, editor : Editor):
    _, jsonText = cmd.split(":", 1)
    data = json.loads(jsonText)
    ord = data["ord"]
    text = data["text"].replace('&nbsp;', ' ')

    note_type = editor.note.note_type()
    note_type_name = note_type["name"]
    fld_name = next(x["name"] for x in note_type["flds"] if x["ord"] == ord)
    if getUserOption('loose_search', refresh=True):
        query = f'note:"{note_type_name}" "{fld_name}:*{text}*"'
    else:
        query = f'note:"{note_type_name}" "{fld_name}:{text}*"'
    col = editor.note.col
    nids = col.find_notes(query)

    options = []
    options_iter = distinct(
        col.get_note(nid).fields[ord]
        for nid in nids
    )
    while len(options) != MAXIMUM_OPTION_AMOUNT:
        option = next(options_iter, None)
        if option is None:
            break
        options.append(option)

    data = {
        "options": options,
        "ord": ord,
    }

    editor.web.eval(f"Autocomplete.update({json.dumps(data)})")

    return True


def load_autocomplete_js(webcontent: aqt.webview.WebContent, context):
    if isinstance(context, Editor):
        addon_package = context.mw.addonManager.addonFromModule(__name__)
        base_path = Path(f"/_addons/{addon_package}/web")

        webcontent.head += f'<script type="module" src="{str(base_path / "autocomplete/autoComplete.js")}"></script>'

        addons_folder = Path(context.mw.addonManager.addonsFolder())
        addons_dir = (addons_folder / addon_package / "web")
        for file in addons_dir.glob('*.js'):
            file = file.relative_to(addons_dir)
            file = base_path / file
            webcontent.js.append(str(file))

        for file in addons_dir.glob('*.css'):
            file = file.relative_to(addons_dir)
            file = base_path / file
            webcontent.css.append(str(file))


def init_webview():
    gui_hooks.webview_will_set_content.append(load_autocomplete_js)
    gui_hooks.webview_did_receive_js_message.append(handle_bridge_commands)
