# Nexus PLM for GIMP — user guide

Everything is in the **Nexus PLM** menu on GIMP's menu bar. Every dialog you see belongs to the
Nexus PLM tray application; the same dialogs appear in every other Nexus PLM add-in, so what you
learn here holds in Inkscape, QGIS and the office suites too.

## Before you start

1. The **Nexus PLM tray application** must be running (the tray icon near the clock). If it is
   not, every command says so in GIMP's error console and stops.
2. **Sign In…** once. The session is shared by every Nexus add-in on the machine and is kept
   between GIMP sessions; **Connection Status** tells you who is signed in.

## The image is the item

An image becomes a PLM item in one of three ways:

- **New from Template…** — pick a type, PLM numbers the item, and the type's template opens in
  GIMP with the part number, revision, description and dates already recorded in it.
- **Open from PLM…** / **Search…** — browse or search the vault; the image you pick opens as
  another image in GIMP. Your current image is left alone.
- **Save As New Item…** — register the image you have open as a new item. **Save As Existing
  Item…** gives its content to an item that already exists instead.

From then on the add-in knows which item the file is, whichever way you open it.

## Working on an item

| Command | What it does |
|---|---|
| **Check Out** | Takes the lock. Nobody else can change the item while you hold it. |
| **Save to PLM** | Saves the image to its file (as XCF) and uploads it as a new version of the revision. You keep the lock. |
| **Check In** | Saves, uploads and releases the lock. You can leave a comment. |
| **Revise** | Starts the next revision — major (A → B) or minor (A → A.001), as the type allows. **The image you are in becomes the new revision**; nothing new opens. |
| **Change Ownership…** | Hands the item to another user. |
| **Properties…** | The item's full card: revisions, workflows, history, approvers, attachments. |
| **Edit Values…** | Edit the item's attributes. Values PLM owns are shown locked; the ones the image owns are editable. What you save is written into the image. |
| **Refresh Values** | Re-read the item's attributes from PLM into the image — after somebody else changed them, or after Revise. |
| **My Worklist…** / **New Workflow…** | What PLM is waiting on you for; start a workflow on this item (this is how a revision gets Released). |

## Where the values go

Every attribute the type maps is written **into the XCF file itself**, as a parasite named
`nexus-plm/attributes`. You will not see it on the canvas and you do not need to: the file carries
its part number and revision wherever it goes, and PLM reads them back from it. You can see it in
GIMP under **Image ▸ Metadata** only indirectly; the add-in's **Properties…** is the place to look.

If the image has a **text layer named after an attribute** — `PartNumber`, `Revision`,
`Description`, `Author`… — the value is written into that layer's text too. Most images will not
have one, and nothing depends on it.

**Export does not carry the record.** A PNG or JPEG you export is a picture; the `.xcf` is the PLM
item. Keep the `.xcf` as the tracked dataset.

## Session and information

**Sign In…** / **Sign Out** · **Current Settings…** (staging folder, service port, where the
service connects) · **Connection Status** (is the service up, who is signed in) · **Help** (this
project's page) · **About** (add-in and service versions).

## If something does not work

- *"Cannot reach Nexus PLM on http://localhost:5100"* — start the Nexus PLM tray application.
- *"This image is not registered in PLM"* — the file is not an item yet. Use **Save As New Item…**
  or open the item from PLM.
- *"Save this image to a file first"* — a never-saved image has no file for PLM to take.
- **No Nexus PLM menu** — GIMP reads its plug-ins at startup; restart it. The plug-in lives in
  the plug-ins folder of your *newest* GIMP profile.
- A command that PLM refuses (checked out to someone else, released revision) says so in PLM's own
  words in a toast.
- The add-in's log is `%APPDATA%\NexusPLM\Logs\plmgimpaddin.log`.
