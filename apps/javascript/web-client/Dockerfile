FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY apps ./apps

RUN corepack enable && pnpm install --frozen-lockfile
RUN pnpm --filter @apps/web-client build

FROM nginx:alpine
COPY --from=build /app/apps/javascript/web-client/dist /usr/share/nginx/html
COPY apps/javascript/web-client/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
