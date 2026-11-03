import fs from 'fs';
import {geoMercator, geoPath, geoArea} from 'd3-geo';
import * as topo from 'topojson-client';
import {createRequire} from 'module';
const require = createRequire(import.meta.url);
const w = JSON.parse(fs.readFileSync(require.resolve('world-atlas/land-50m.json')));
const land = topo.feature(w, w.objects.land);
const W=1000,H=1100;
const bbox = {type:'Polygon',coordinates:[[[61,5],[61,37.5],[93,37.5],[93,5],[61,5]].reverse()]};
const proj = geoMercator().fitExtent([[20,20],[W-20,H-20]], {type:'MultiPoint',coordinates:[[61,6],[93,37]]});
proj.clipExtent([[-50,-50],[W+50,H+50]]); const path = geoPath(proj).digits(1);
// clip land by rendering full then using svg clip; just output path
const landD = path(land);
// approximate Mauryan extent c.250 BCE (lon,lat), counter-clockwise ring per d3 convention handled by reversing if needed
const ring = (pts)=>{let g={type:'Polygon',coordinates:[[...pts, pts[0]]]}; if(geoArea(g)>2*Math.PI) g.coordinates[0].reverse(); return g;};
const empire = ring([[61.5,31],[64,35],[69,36.5],[73,36.5],[75.5,34.5],[78.5,31.5],[81,30],[84,28.4],[88,26.8],[89.8,26],[90,22],[89,20.8],[87.5,21],[86,19],[84.5,17.5],[82.8,16],[81.5,15],[80.5,14.2],[79.5,13.6],[77.5,13.2],[75.5,13.4],[74,13.8],[73,14.5],[72,17],[71.5,20],[68.5,20.5],[67.5,23.5],[66.5,25],[64.5,27],[62,29]]);
const kalinga = ring([[87.6,21.4],[86,19],[84.5,17.5],[83.2,17.4],[82.3,18.3],[82,19.8],[83,21],[84.5,22],[86.3,22.6],[87.6,22.3]]);
const sites = {
 'Shahbazgarhi':[72.16,34.24],'Mansehra':[73.20,34.33],'Kandahar':[65.71,31.61],'Kalsi':[77.85,30.52],
 'Girnar':[70.49,21.52],'Sopara':[72.79,19.42],'Dhauli':[85.84,20.19],'Jaugada':[84.82,19.52],
 'Erragudi':[77.62,15.20],'Maski':[76.65,15.96],'Brahmagiri':[76.80,14.83],'Rupnath':[80.05,23.65],
 'Bairat':[76.20,27.45],'Sanchi':[77.74,23.48],'Sarnath':[83.02,25.38],'Delhi-Topra':[77.24,28.64],
 'Lauriya Nandangarh':[84.40,27.00],'Lumbini':[83.28,27.47],'Pataliputra':[85.13,25.60]};
const out = {W,H,land:landD,empire:path(empire),kalinga:path(kalinga),
  sites:Object.fromEntries(Object.entries(sites).map(([k,v])=>[k,proj(v)])),
  kalingaCenter:proj([84.6,20.3]), south:proj([78,10.5]), empireLabel:proj([78.5,24.5])};
const OUT = process.argv[2] || 'map.json';
fs.writeFileSync(OUT, JSON.stringify(out));
console.log(landD.length, out.kalingaCenter, out.sites.Dhauli);
