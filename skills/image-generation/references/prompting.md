# Prompting

A prompt is the art direction written for a model. Every prompt is built from `art-direction.md`, so two prompts for the same territory should read like siblings.

## The recipe

Write in this order, as plain descriptive sentences rather than tag soup:

1. **Subject**: who or what, doing what. Be concrete: "a woman in her fifties checking a delivery tablet at a loading bay", not "a person working".
2. **Setting**: place, time of day, season, and the specific details that say where we are. For APAC clients, name the city type and architecture honestly rather than defaulting to a generic Western office.
3. **Composition**: framing, camera height, where the subject sits in the frame, and where the negative space goes for copy. Match the placement's aspect ratio.
4. **Light and lens**: light source, direction and quality, focal length feel, depth of field.
5. **Palette and material**: describe the vault tokens in words (for example "deep ink blue with one warm coral accent") and the textures.
6. **Mood**: one or two words, taken from the territory.
7. **Exclusions**: where the model supports a negative prompt, add the shot's items from the art direction's "never" list.

## Per provider

- **Recraft**: choose vector or raster output explicitly. Pass the client's custom style for anything in a system. Keep prompts shorter, because the style carries the look.
- **Replicate**: parameters differ by model, so read the model's input schema (the Replicate connector returns it) before the first run. Set aspect ratio, output format and seed explicitly. Keep the parameters fixed within a set and change only the prompt.

## Consistency

- Hold seed, model version, style and parameters constant across a set, and vary only the subject line.
- Keep a prompt block in `art-direction.md` for each territory and copy from it. Never retype.
- When one option wins, derive from it (variation or image-to-image) rather than regenerating from scratch.

## Never in a prompt

- A real person's name or likeness, a celebrity, or a client's staff.
- A living artist's name, "in the style of" any named artist or studio, or a film, game or franchise.
- A brand, logo, trademark or product name, including the client's own. Logos and names are set on top of the image, never generated into it.
- Unannounced product details or the real name of a stealth client. Use the codename.
- Filler words that carry no direction: "award-winning", "trending", "8k", "masterpiece", "hyper-detailed".

## Casting

Write casting explicitly in art direction: age range, the mix of people across the set, clothing register, body language. Review every set as a whole for stereotypes before selecting. The panel's Brand-integrity lens checks this.
