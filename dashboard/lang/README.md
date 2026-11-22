# Dashboard translations

Each file here is one language for the EasyServer dashboard. The dashboard offers every file it finds in this
folder in its language menu (login screen and the bottom of the sidebar), so **adding a language is adding a file**.

```json
{
 "language": "Deutsch",
 "strings": {
  "Save": "Speichern",
  "Restart {}": "{} neu starten",
  "{} free of {}": "{} frei von {}"
 }
}
```

- The file name is the language code: `de.json`, `es.json`, `pt-br.json` …
- `language` is the name shown in the menu, in that language.
- In `strings`, the left side is the English text exactly as the dashboard shows it, the right side is the translation.
- `{}` stands for something filled in (a name, a number, a size). Keep the same number of `{}`. To change their
  order, number them: `"{} free of {}": "{2} von {1} frei"`.
- Anything missing from the file, or left empty, stays in English - nothing breaks.
- Product names (BeamMP, Discord, AuthKey, Wake-on-LAN …) and commands like `/kick` stay as they are.

To fix a word: open the file on GitHub, click the pencil, change the right side, and propose the change.
