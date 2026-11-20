# The story layer

On https://book.ozarland.com/ the book is told as a crossing: **LUMO**, the travelling cartographer of OzarLand,
walks with an operations team across an archipelago where the mist is the loss of control. Each chapter opens
with the place LUMO reaches and closes with the road to the next stop.

**The text of the book is not changed.** `tools/site/build.py` converts `chapters/` and `appendices/` with pandoc
and fails if the published text of a page differs from the book. Only the navigation is adapted: the *Part* label
above a chapter becomes the story header, and the *Previous / Contents / Next* line becomes the road on.

## Files

- `story.json` — the story, page by page: the place, the scene, the state of LUMO's lantern (the control spectrum
  of Chapter 5: Unknown, Visible, Understood, Controlled, Recoverable, Sustainable), what LUMO carries away, the
  road on, and the position of the stop on the map. Every page of `chapters/` and `appendices/` has an entry; the
  build fails otherwise.
- `art/` — the art direction (`direction-artistique.md`, in French), the palette, the generation prompts of the
  cover, the map, the opening, the twenty chapter openings and the conclusion, and the reference images of LUMO and
  of the island style.
- `../site/assets/story/` — the images used by the site: the cover and the map are direction concepts, not print
  masters.

## Rules from the art direction

- LUMO observes, lights, verifies and passes on knowledge. LUMO never fixes the platform alone, never decides for the
  team, never uses magic. The people make the decisions.
- The mist is never a monster. Scenes stay calm, including incidents.
- A scene never adds a technical fact, a command or an outcome that the chapter does not contain. The chapter is the
  source of truth; the story only frames it.
- Titles, place names and numbers are typeset, never painted. The state of the lantern is always written in words
  and drawn as a shape, never carried by colour alone.
- Motion happens once, on arrival, and is switched off under `prefers-reduced-motion`.

## Adding the chapter illustrations

The prompts in `art/prompts/` are ready. When an opening illustration is generated and checked against the chapter,
save it as `site/assets/story/scenes/<page file name>.webp` (for example `01-openstack-doesnt-end-at-deployment.webp`)
and reference it from the page's entry in `story.json` with `"image"` and `"image_alt"`.
