# Agency standards — client website builds

The single source of truth for how client websites are built and delivered.

| File | Who reads it |
|---|---|
| CLAUDE.md | Claude Code, automatically, when working in a repo |
| PROJECT-INSTRUCTIONS.md | Paste into a Claude Project's custom instructions |

Both describe the same standard. Claude Code in the terminal reads CLAUDE.md on
its own; Claude in chat does not — so a developer building in chat only gets
the standard if it's in the Project instructions.

## Developer setup — once

1. Create a Claude Project called "Client Websites"
2. Copy everything below the horizontal line in PROJECT-INSTRUCTIONS.md into
   the Project's custom instructions
3. Done. No GitHub connector needed.

Or tell Claude in a chat:

    Fetch https://raw.githubusercontent.com/umarmalik01/agency-standards/main/PROJECT-INSTRUCTIONS.md
    and follow it for this build.

## Building a client site

1. Open a NEW chat inside the Project — one chat per client
2. Paste the client's business information: name, what they do, phone,
   WhatsApp, email, address, pages needed, brand colours
3. Claude produces three variants and a zip named after the client
4. Download the zip

## Deploying the preview

1. Open the agency dashboard, go to Client previews
2. Drag the zip onto the upload area
3. Check the card — red means something needs fixing
4. Press Deploy everything
5. Send the client their link

The zip filename becomes the web address: swift-lease.zip, lowercase, hyphens.

## When the client approves

Tell Claude which variant they chose. It generates the cPanel build from that
variant, with the PHP admin panel. Upload to cPanel. Then remove the client
from the previews page and deploy again to clear the preview.

## Two things that are not negotiable

**Images are always local files.** Never external, never hotlinked from the
client's old site. Each variant carries its own assets/img/ folder.

**Photographs are real.** No generated artwork or decorative placeholders
standing in for photos. Until real photos arrive, image slots stay as plain
grey boxes labelled with the filename.

## Hosting

Cloudflare Pages holds previews only. Every approved live site goes to cPanel,
because the client admin panel is PHP. This split is permanent.

## Changing the standard

Edit the file here and commit. Keep both files in step — if you change one,
change the other.

Never put client contracts, invoices, ID copies, passwords or API tokens in
this repo. Standards only.
