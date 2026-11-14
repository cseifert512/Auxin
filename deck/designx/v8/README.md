# v8: the deck as a page that is scrolled

The first version of ours. One page, no slides. Scrolling is the only control, and it moves time: years in the room, hours on its floor, seconds at the mill. A clock at the top right says what the scroll is moving.

Open it with `node deck/serve.mjs`, then http://localhost:5312/designx/v8.

## The order, and why

It follows a reading of v7 given to Clay on 14 November 2026 and not yet agreed by him: show the whole before taking it apart, tell one case through instead of describing a system, and keep the generated pictures away from the drawings.

| Part | What it is | Scroll moves |
|---|---|---|
| The name | "Buildings that grow. And the means to make many." | |
| Why | The severance sentence, which v7 keeps for its last slide | |
| A room, through time | The whole, first: one room from above, on the approach and inside | The design, assembly, planting, establishing, a year of seasons |
| What makes it hard | The premise, then the variability sentence | |
| Growth changes the light | Three plans of the floor, at three ages | One midsummer day, 6 am to 6 pm |
| Planting becomes part of the room | The room unrolled, still | |
| The plants found the joints | The case, in five sentences and one plate | |
| Different parts. A repeatable process. | Daniel's line, playing by itself | |
| Form. Measure. Machine. | Three of his stations | 34 seconds at each |
| What is not designed yet | The planting | |
| The first customers, the three steps, the two of us, the close | As v7 has them | |

Left out of v7 on purpose: the four slides that diagram a learning loop (9, 10, 11 and 15) and the commercial loop (14). The joints case stands where they stood.

## Whose words

Taken from v7 as they are: the title and its second line, the severance sentence, the variability sentence, the scene titles "Growth changes the light" and "Planting becomes part of the room" (from v7's lines for those tabs on slide 4), the factory titles and captions, everything about customers, price and the two founders, and the close.

New here, for Clay to keep, change or cut:

- "A building like this is not finished when it is built. Nobody can yet draw, promise or price one whose finished state is years away, and partly not theirs to decide." This stands where v7 says "The obstacle is production."
- "A room, through time." and the five notes under it.
- "The plants found the joints." and its five sentences. The numbers are from the runs and the model: 631 milled joints, 13 reached in all three runs and 9 more in some, a slot 3 mm by 110 mm, a 30 mm land opening 40 mm, 18 laps cut splayed.
- "Every study here changed the building and held the planting still. Which plant goes where, and why, is the next thing to design."
- "A splayed lap is one more." under Machine.
- The small line above each title, the line about scrolling on the first screen, and the note under the light.

Every scene keeps its statement of what it is not: a growth scenario and not a forecast; simulated and not built; studies and not an operating line.

## How it is made

- `index.html` is the page, `site.css` its look, `site.js` the scroll. No library, nothing built.
- A scene is a tall stretch of page with a stage pinned in it. How far the stretch has been scrolled picks the moment. In the room and the light that is a picture from `frames/`, blended into the next. At the mill it is a time sent to one of Daniel's drawings (`../5/factory/`), which draw themselves when told.
- `frames/` is copied from `drawings-in-code/exports/deck/` by `node deck/pieces.mjs`. Nothing is worked out when the page is shown.
- It shares the typefaces (`../4/`), Daniel's drawings (`../5/factory/`) and the photographs (`../assets/`, `../3/assets/`) with the copied editions, so it has to stay beside them.

## Not done

- **No page for paper.** Printed, each pinned scene would show one moment. The application takes a file, so this version cannot be what is uploaded until it has a print layout and a way to export one.
- **The room's pictures were made for a slide**, 2234 pixels wide for three views. A page this size wants each view made larger, and more moments than 34.
- **The frames are 14 MB**, all asked for as their scene comes near. Fine from this laptop, heavy over a slow connection.
- **Opened from disk without the server**, the factory drawings and the frames should still work, but that has not been tried.
