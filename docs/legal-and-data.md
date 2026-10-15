# Legal, licensing, and data-handling notes

SceneSeek is an identification tool, not a video-hosting service. The repo ships the application code and a blank reference-collection structure, not a library of movies, anime episodes, clips, posters, subtitles, or copyrighted promotional material.

## Upload rules

- v1 accepts local screenshots and clips only. It intentionally does not fetch or scrape Instagram Reels, TikTok videos, YouTube videos, or other social links.
- Users should upload material they have the right to submit. Before a public launch, display a concise notice about allowed use and a reachable rights-holder contact.
- Uploaded media is transient, named using random identifiers, and removed after successful/terminal processing. The local worker performs TTL cleanup; cloud deployments also need provider-side bucket retention for interruptions.

## Reference collection

Every title folder should contain a metadata file with provenance/attribution. For each frame, record source URL, applicable license or documented legal basis, capture date if useful, attribution requirements, and restrictions. Suitable starting points may include explicitly public-domain/Creative Commons media or content you own and are entitled to process. Confirm the precise item and jurisdiction; a website being free to view does not make every asset free to redistribute or embed.

Do not treat this project README as legal advice. Copyright exceptions vary by country and factual circumstances. Obtain permission where required and remove disputed material while a takedown request is reviewed.

## Metadata and posters

AniList, Jikan/MyAnimeList, TVmaze, and OMDb are optional metadata sources and have their own terms, quotas, attribution rules, and rate limits. Re-check each provider's current policies. Do not expose OMDb or Supabase keys to the browser. A metadata provider search does not constitute evidence that the uploaded scene depicts the returned title.

## Removal requests

The API has a `POST /v1/takedown` intake endpoint. A real deployment must publish the contact workflow and actually review and action those submissions; merely recording a request is not a completed takedown process.


## Third-party lookups

When `ENABLE_ONLINE_ANIME=true`, sampled frames (max 3 per upload) are sent to trace.moe for scene matching and queries to AniList for metadata. Disclose this in your privacy notice or disable it. `/v1/search` sends the typed query to AniList, TVmaze and Apple iTunes Search (and OMDb if configured).
