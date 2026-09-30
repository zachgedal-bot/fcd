FROM node:22-alpine
WORKDIR /app
COPY package.json ./
COPY server ./server
COPY after-hours.html after-hours.css after-hours.js after-hours-ui.js enter.html config.js ./
COPY altitude_edge/venues.json altitude_edge/fc_ratings_nwsl.json altitude_edge/fixtures_demo.json ./altitude_edge/
COPY altitude_fc/altitude_fc_cards.html altitude_fc/evidence_table.json altitude_fc/evidence_table.csv altitude_fc/evidence_table.md altitude_fc/model_hir_curves.png ./altitude_fc/
ENV NODE_ENV=production PORT=8080
EXPOSE 8080
USER node
CMD ["node", "server/server.js"]
