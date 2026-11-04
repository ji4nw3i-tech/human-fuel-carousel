# The Human Fuel — daily carousel bot

Builds an 8-slide Instagram carousel for [@thehumanfuel.farmacy](https://www.instagram.com/thehumanfuel.farmacy/) about natural farming, plant-based eating, and practical health, and posts it with the official Instagram API.

Adapted from [kingsleylow123/news-blotato-autopost](https://github.com/kingsleylow123/news-blotato-autopost) (MIT).

## How a run works

1. `scraper.py` pulls stories from Google News queries and the RSS feeds in `config.json`, and resolves Google News links to the real article.
2. `selector.py` has Claude score the stories against the brand brief (5 content pillars, rotated so no pillar runs twice in a row), then write the hook, 5 slides, sources and caption. A draft is rejected if it uses a number not in the source, a cure claim, a hook over 12 words or a slide over 30 words.
3. `image_gen.py` finds a food photo per slide on Pixabay (or Pexels), skipping photos tagged with people or meat.
4. `builder.py` renders the slides with Playwright.
5. `hosting.py` commits JPEG copies to `published/` in this repo so Instagram can download them.
6. `poster.py` publishes the carousel; `logger.py` records the story in `posted_urls.json` so it is not reused.

## Keys

Never put keys in this repository. The bot reads them from environment variables:

| Variable | Used for |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude (scoring and writing) |
| `PIXABAY_API_KEY` or `PEXELS_API_KEY` | Slide photos |
| `INSTAGRAM_ACCESS_TOKEN` | Posting (Meta system-user token, never expires) |

Locally they come from `.env` or any `*human-fuel*.txt` file in iCloud Drive. On GitHub Actions they come from repository secrets.

## Run it

```bash
python pipeline.py --dry-run   # build slides only, into ~/Downloads/carousels/
python poster.py               # check the Instagram connection, posts nothing
python pipeline.py             # build and post
```

The scheduled workflow (`.github/workflows/human-fuel-carousel.yml`) runs daily at 12:37 UTC (8:37pm Malaysia time). With `CASHFLOWOS_URL` and `CONTENT_SECRET` set, it sends the slides to Telegram and posts only after you tap Approve.
