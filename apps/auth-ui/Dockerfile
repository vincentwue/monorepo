FROM node:20-alpine AS build
WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY apps ./apps

RUN corepack enable && pnpm install --frozen-lockfile
RUN pnpm --filter @apps/auth-ui build

FROM nginx:alpine
COPY --from=build /app/apps/auth-ui/dist /usr/share/nginx/html
COPY apps/auth-ui/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
