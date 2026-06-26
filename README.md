# Instagram Follow-Back Comparator

This is a small local Python workflow for comparing Instagram followers and following lists from saved Chrome HTML.

## Capture The Inputs

1. In Google Chrome, open Instagram and go to your profile.
2. Open the `Followers` modal.
3. Scroll inside the modal until the full list is loaded.
4. Save the page as `input/followers.html` using `Ctrl/Cmd+S`.
5. Open the `Following` modal.
6. Scroll inside the modal until the full list is loaded.
7. Save the page as `input/following.html` using `Ctrl/Cmd+S`.

Chrome's `Webpage, Complete` and `HTML Only` save options are both fine. The script only reads the `.html` file.

## Run

```bash
python3 compare_instagram_follows.py input/followers.html input/following.html
```

Optional:

```bash
python3 compare_instagram_follows.py input/followers.html input/following.html --show-counts --debug-samples
```

## Outputs

The script writes:

- `output/followers.txt`
- `output/following.txt`
- `output/not_following_back.txt`

If the script says it found username-like values on the whole page but not inside a modal, re-save the page while the Followers or Following modal is open. A normal Instagram home/profile save can include feed authors, suggested accounts, and navigation data, so the script refuses to compare that unsafe input.

## Test

```bash
python3 -m unittest test_compare_instagram_follows.py
```
