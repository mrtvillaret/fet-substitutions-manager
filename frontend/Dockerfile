FROM node:20-alpine AS build

WORKDIR /app
# npm ci en lloc de npm install: instal·la exactament el que diu el lock i
# s'atura amb error si el lock i el package.json no concorden, en lloc de
# resoldre versions noves silenciosament. El lock és obligatori (sense *).
COPY package.json package-lock.json /app/
RUN npm ci
COPY . /app
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
