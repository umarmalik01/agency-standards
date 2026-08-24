# CLAUDE.md — client website builds

Guidance for Claude Code when building client websites for a web design agency
in Dubai. Follow this standard on every build, without being asked.

This is the terminal-read twin of PROJECT-INSTRUCTIONS.md. Both must say the
same thing: Claude Code reads this file automatically inside a repo; Claude in
chat reads PROJECT-INSTRUCTIONS.md. If you change one, change the other.

## Always respond in English

The developer may write in Hindi, Urdu, Roman Urdu or a mix. Your output is
always English.

## The one-message workflow

A client brief arrives in a single message. From that one message, produce the
full deliverable — do not drip work out over many turns, do not stop to ask
permission for each step. Ask only for missing business details; build first,
refine after the client has seen it.

From one message, deliver:

1. **Three design variants — v1, v2, v3.** Genuinely different: different colour
   system, different type pairing, different layout structure. Not three
   recolours of one design. Each is a complete, self-contained site with every
   page the client needs. No shared folders between variants.
2. **A chooser page** — `index.html` at the top level listing the three options,
   each with a short description and a link into that variant.
3. **Regenerate the index** with `gen-index.js` so the internal preview list
   stays current.
4. **Commit and push.**
5. **A zip named after the client slug** — `swift-lease.zip`, not
   `website.zip`. The zip holds `v1`, `v2`, `v3` at its top level plus the
   chooser `index.html`. That filename becomes the client's web address:
   lowercase, hyphens only.

## Build rules

- Static HTML, CSS, vanilla JS. No frameworks, no build step, no npm.
- Mobile-first. Check the layout at 390px. No horizontal overflow.
- Contact forms have no backend. JS composes a WhatsApp message and opens
  `wa.me` with the client's number.
- Every client's design must look different from the last. Avoid the default
  navy-and-orange corporate look.
- Real headings in order, alt text on every image, visible focus states,
  `prefers-reduced-motion` respected.

## Image rules — never break these

- **Never reference an image by external URL.** Not from the client's old site,
  not from any domain. A build that hotlinked a client's old WordPress uploads
  showed nothing but broken images once deployed. Every variant folder gets its
  own `assets/img/` folder, and every `img` src is a relative path like
  `assets/img/hero.jpg`.
- **Never use generated artwork as site imagery.** No illustrations, no CSS
  textures, no gradient "branded placeholders". Real sites use real photographs
  of the actual business — the building, the villas, finished work, workers on
  site.
- **When real photos aren't available yet,** leave image slots as plain neutral
  grey boxes with the filename written in them. Nothing decorative. Then ask the
  developer for real photos: the client's own job photos are best, otherwise
  free stock downloaded from Pexels, Unsplash or Pixabay. You cannot download
  photos yourself.
- **Ship an image map** in the README listing every filename, where it appears,
  and the recommended pixel size — so a photo can be swapped by overwriting the
  file, with no code changes.

## Hosting — this split is permanent

- **Previews → Cloudflare Pages**, uploaded through the Client previews page in
  the agency dashboard. Previews only.
- **Live site → cPanel, always.** Every final site ships with a PHP admin panel,
  and Cloudflare Pages cannot run PHP. Never collapse these two.

## The client admin panel

Ships with every live site. The client logs in at `/admin/` and controls:

- **Tracking:** GTM (recommend as the primary container), plus GA4, Meta Pixel,
  TikTok Pixel, and custom head/body code.
- **Per-page SEO:** title, description, OG image, canonical, noindex.
- **Business info:** name, phone, WhatsApp, email, address — updating site-wide.

The client sets their own password on first visit. Never ship a default
password.

## Approval flow

The developer will say something like "client approved v2".

Generate the cPanel build **from that approved variant's files**. Never rebuild
by hand — the live site must be pixel-identical to the approved preview.

- Convert pages to `.php`
- Add the admin panel, `.htaccess`, `robots.txt`, `sitemap.xml`
- Zip with files at **root level**, ready to extract straight into `public_html`

After the client is live, remove them from the previews page and deploy again to
clear the preview.

## What never goes in this repo

Standards only. Never commit client contracts, invoices, ID copies, passwords,
API tokens, the PHP admin module source, or client data.
