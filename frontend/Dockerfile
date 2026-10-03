FROM node:22-alpine AS build

WORKDIR /app
# npm ci en lloc de npm install: instal·la exactament el que diu el lock i
# s'atura amb error si el lock i el package.json no concorden, en lloc de
# resoldre versions noves silenciosament. El lock és obligatori (sense *).
COPY package.json package-lock.json /app/
RUN npm ci
COPY . /app
# Subruta on es publicarà (p.ex. /demo/); per defecte, l'arrel del domini.
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=$VITE_BASE_PATH
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
