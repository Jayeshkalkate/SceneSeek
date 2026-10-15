# Render deployment troubleshooting

## Why the API URL may show JSON

`https://<api-service>.onrender.com/` is the Django API service. Its root route is API metadata, not the Next.js website. The user-facing site is served by the separate `sceneseek-web` service.

This project uses `render.yaml` as a Blueprint for two web services:

- `sceneseek-api`: Dockerfile `Dockerfile.render`, API endpoints and worker.
- `sceneseek-web`: Dockerfile `apps/web/Dockerfile`, Next.js website on port 3000.

The API root redirects to `FRONTEND_URL` when that environment variable is set. The Blueprint's default is `https://sceneseek-web.onrender.com`; update it if the service URL differs or you use a custom domain.

## Deployment checklist

1. Render Dashboard → **New → Blueprint** → select the GitHub repository and branch containing `render.yaml`.
2. Confirm both services exist. Do not create duplicate services if they are already managed by the Blueprint.
3. Set API `DATABASE_URL` to a reachable PostgreSQL connection string for hosted deployment.
4. Set API `CORS_ORIGINS` to the exact frontend origin, such as `https://sceneseek-web.onrender.com` (no trailing slash or path).
5. Set API `FRONTEND_URL` to the frontend's public URL.
6. Set web `NEXT_PUBLIC_API_URL` to the API's public URL, such as `https://sceneseek-api.onrender.com`.
7. Deploy/redeploy the web service after changing `NEXT_PUBLIC_API_URL` because it is supplied during the Docker build.
8. Open the web service URL and test upload → queued job → result polling. Test API health at `/ping` and interactive docs at `/docs`.
9. If the website fails, open `sceneseek-web` → Events and Logs and inspect the first build/runtime error. If the website loads but API calls fail, inspect browser Network/Console and verify API URL and CORS.

## Common symptoms

- **JSON at API root:** expected for API service unless `FRONTEND_URL` redirect is configured. Open the web service URL.
- **Frontend calls localhost:** `NEXT_PUBLIC_API_URL` was missing/wrong during build; set it and redeploy the web service.
- **CORS error:** add the exact web origin to API `CORS_ORIGINS`, then redeploy the API.
- **Build fails:** verify Docker context is repository root and Dockerfile is `apps/web/Dockerfile` for the web service; inspect logs for dependency or TypeScript errors.
- **Upload accepted but never finishes:** inspect worker status, database connectivity, shared storage, and API logs. A live web service alone does not prove worker processing is healthy.
