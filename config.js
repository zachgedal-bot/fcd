/* Default front-end config for static hosting. When served by server/server.js this file is
   replaced by a dynamic /config.js that points fixturesUrl at the live adapter. */
window.AFTER_HOURS_CONFIG = {
  gate: true,                                      // static hosting: cosmetic invite overlay. The server replaces this with a real session gate.
  fixturesUrl: 'altitude_edge/fixtures_demo.json', // static hosting: demo lines, clearly labelled
  propsUrl: null,
  dataBase: '',
  homeUrl: 'index.html',
  labUrl: 'altitude_fc/altitude_fc_cards.html',
  serverGated: false
};
