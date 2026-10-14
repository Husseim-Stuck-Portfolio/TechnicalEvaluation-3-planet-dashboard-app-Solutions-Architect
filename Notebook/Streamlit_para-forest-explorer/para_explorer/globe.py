"""Interactive 3-D globe (MapLibre GL JS v5, globe projection) rendered inside Streamlit.

Why MapLibre instead of folium/pydeck: it gives a real rotating globe, image overlays for the
composites, GeoJSON overlays for patches / Planet footprints, click popups and in-map controls -
and everything is data we hand it from Python (one JSON config), so the map needs no server.

Basemap: EOX "Sentinel-2 cloudless" (Copernicus-based, matches the CDSE theme) or Esri World Imagery.
"""
from __future__ import annotations

import json

from . import config as C

MAPLIBRE_VERSION = "5.20.0"
CDN = f"https://cdn.jsdelivr.net/npm/maplibre-gl@{MAPLIBRE_VERSION}/dist"

BASEMAPS = {
    "Sentinel-2 cloudless (EOX / Copernicus)": {
        "tiles": ["https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg"],
        "maxzoom": 13,
        "attribution": "Sentinel-2 cloudless by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2020)",
    },
    "Esri World Imagery": {
        "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        "maxzoom": 18,
        "attribution": "Tiles &copy; Esri - Esri, Maxar, Earthstar Geographics",
    },
}

_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8">
<link href="__CDN__/maplibre-gl.css" rel="stylesheet">
<style>
  html,body{margin:0;height:100%;background:#050912;font-family:system-ui,-apple-system,Segoe UI,sans-serif}
  #map{position:absolute;inset:0;background:radial-gradient(circle at 50% 40%,#0b1730 0%,#050912 70%)}
  .hud{position:absolute;color:#E8EEF6;background:rgba(10,17,29,.82);border:1px solid rgba(255,255,255,.12);
       border-radius:10px;padding:8px 11px;font-size:12px;backdrop-filter:blur(6px);z-index:5}
  #info{left:10px;top:10px;max-width:290px}
  #info b{font-size:13px} #info .m{color:#9fb0c6;margin-top:2px}
  #ctrl{right:10px;top:10px;display:flex;flex-direction:column;gap:6px;width:150px}
  #ctrl button{background:#152238;color:#E8EEF6;border:1px solid rgba(255,255,255,.14);border-radius:7px;
       padding:6px 8px;cursor:pointer;font-size:12px;text-align:left}
  #ctrl button:hover{border-color:#19D3C5;color:#19D3C5}
  #ctrl label{font-size:11px;color:#9fb0c6} #ctrl input[type=range]{width:100%;accent-color:#19D3C5}
  #coord{left:10px;bottom:46px;font-variant-numeric:tabular-nums;color:#9fb0c6}
  #legend{right:10px;bottom:46px;max-width:230px}
  #legend i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:6px;vertical-align:-1px}
  .maplibregl-popup-content{background:#0F1826;color:#E8EEF6;border:1px solid rgba(255,255,255,.14);
       border-radius:8px;font-size:12px;padding:8px 10px}
  .maplibregl-popup-tip{border-top-color:#0F1826!important;border-bottom-color:#0F1826!important}
  .maplibregl-popup-close-button{color:#E8EEF6}
  #err{left:50%;top:50%;transform:translate(-50%,-50%);display:none}
</style></head><body>
<div id="map"></div>
<div class="hud" id="info"></div>
<div class="hud" id="ctrl">
  <button id="bSpin">&#8635; Rotate globe</button>
  <button id="bFocus">&#9678; Focus area of interest</button>
  <button id="bTilt">&#9650; Toggle 3-D tilt</button>
  <div id="opv" style="color:#9fb0c6;font-size:11px;padding:2px 4px">Overlay opacity: __OPACITY__ % (sidebar)</div>
</div>
<div class="hud" id="coord">lon / lat</div>
<div class="hud" id="legend"></div>
<div class="hud" id="err">The map library could not be loaded (offline?).</div>
<script src="__CDN__/maplibre-gl.js"></script>
<script>
const CFG = __CONFIG__;
(function(){
if(typeof maplibregl==='undefined'){document.getElementById('err').style.display='block';return;}
const aoiC = CFG.center; let spinning=false, tilted=false, userTouched=false;
const style = {
  version:8, projection:{type:'globe'},
  sources:{ base:{type:'raster',tiles:CFG.basemap.tiles,tileSize:256,maxzoom:CFG.basemap.maxzoom,attribution:CFG.basemap.attribution}},
  layers:[{id:'base',type:'raster',source:'base'}]
};
let cam=null; if(CFG.restore && !CFG.autorotate){ try{cam=JSON.parse(sessionStorage.getItem('pe_cam')||'null');}catch(e){} }
const map = new maplibregl.Map({container:'map',style:style,
  center:CFG.autorotate?[aoiC[0]+40,12]:(cam?cam.center:aoiC), zoom:CFG.autorotate?1.3:(cam?cam.zoom:CFG.zoom),
  pitch:cam?cam.pitch:0, bearing:cam?cam.bearing:0, maxPitch:75, attributionControl:{compact:true}});
map.on('moveend',()=>{ try{ if(!spinning) sessionStorage.setItem('pe_cam',JSON.stringify({center:map.getCenter().toArray(),zoom:map.getZoom(),pitch:map.getPitch(),bearing:map.getBearing()})); }catch(e){} });
window.__map = map; map.on('error',e=>console.log('MLERR '+(e.error&&e.error.message)));
map.addControl(new maplibregl.NavigationControl({visualizePitch:true}),'bottom-right');
map.addControl(new maplibregl.ScaleControl({unit:'metric'}),'bottom-left');


function spin(){ if(!spinning) return; const c=map.getCenter(); c.lng-=0.35;
  map.easeTo({center:c,duration:1000,easing:n=>n}); }
map.on('moveend',()=>{ if(spinning) spin(); });
['mousedown','touchstart','wheel'].forEach(ev=>map.on(ev,()=>{ if(spinning){spinning=false;} userTouched=true; }));
function focusAoi(){ spinning=false; map.flyTo({center:CFG.focus?CFG.focus.center:aoiC, zoom:CFG.focus?CFG.focus.zoom:CFG.zoom,
  pitch:tilted?55:0, bearing:0, duration:4200, essential:true}); }
function rotate(){ spinning=true; map.flyTo({center:[aoiC[0]+30,10],zoom:1.3,pitch:0,duration:2500}); }
document.getElementById('bSpin').onclick=rotate;
document.getElementById('bFocus').onclick=focusAoi;
document.getElementById('bTilt').onclick=()=>{ tilted=!tilted; map.easeTo({pitch:tilted?55:0,duration:900}); };
map.on('mousemove',e=>{document.getElementById('coord').textContent=e.lngLat.lng.toFixed(4)+' , '+e.lngLat.lat.toFixed(4);});

document.getElementById('info').innerHTML = CFG.info;
document.getElementById('legend').innerHTML = CFG.legend;

map.on('load',()=>{
  if(CFG.overlay){
    map.addSource('overlay',{type:'image',url:CFG.overlay.url,coordinates:CFG.overlay.coordinates});
    map.addLayer({id:'overlay',type:'raster',source:'overlay',paint:{'raster-opacity':CFG.opacity/100,'raster-fade-duration':0,'raster-resampling':'nearest'}});
  }
  map.addSource('pin',{type:'geojson',data:{type:'Feature',geometry:{type:'Point',coordinates:aoiC}}});
  map.addLayer({id:'pin-halo',type:'circle',source:'pin',maxzoom:7,paint:{'circle-radius':13,'circle-color':'#19D3C5','circle-opacity':0.18,'circle-stroke-color':'#19D3C5','circle-stroke-width':1}});
  map.addLayer({id:'pin',type:'circle',source:'pin',maxzoom:7,paint:{'circle-radius':4.5,'circle-color':'#19D3C5','circle-stroke-color':'#fff','circle-stroke-width':1.5}});
  map.addSource('aoi',{type:'geojson',data:CFG.aoi});
  map.addLayer({id:'aoi-fill',type:'fill',source:'aoi',paint:{'fill-color':'#19D3C5','fill-opacity':CFG.overlay?0:0.07}});
  map.addLayer({id:'aoi-line',type:'line',source:'aoi',paint:{'line-color':'#19D3C5','line-width':2,'line-dasharray':[2,1]}});
  if(CFG.patches){
    map.addSource('patches',{type:'geojson',data:CFG.patches});
    map.addLayer({id:'patches-fill',type:'fill',source:'patches',paint:{'fill-color':'#E66767','fill-opacity':0.30}});
    map.addLayer({id:'patches-line',type:'line',source:'patches',paint:{'line-color':'#ff9a9a','line-width':1.2}});
    map.addLayer({id:'patches-hl',type:'line',source:'patches',filter:['==',['get','patch_id'],CFG.highlight_patch||-1],
      paint:{'line-color':'#ffffff','line-width':3.5}});
  }
  if(CFG.scenes){
    map.addSource('scenes',{type:'geojson',data:CFG.scenes});
    map.addLayer({id:'scenes-fill',type:'fill',source:'scenes',paint:{'fill-color':'#3987e5',
      'fill-opacity':['interpolate',['linear'],['coalesce',['get','cloud'],50],0,0.30,100,0.03]}});
    map.addLayer({id:'scenes-line',type:'line',source:'scenes',paint:{'line-color':'#86b6ef','line-width':1,
      'line-opacity':['interpolate',['linear'],['coalesce',['get','cloud'],50],0,0.95,100,0.25]}});
    map.addLayer({id:'scenes-hl',type:'line',source:'scenes',filter:['==',['get','id'],CFG.highlight_scene||''],
      paint:{'line-color':'#ffffff','line-width':3.5}});
  }
  const popup=new maplibregl.Popup({closeButton:true,maxWidth:'260px'});
  function bind(layer,fmt){
    if(!map.getLayer(layer)) return;
    map.on('click',layer,e=>{popup.setLngLat(e.lngLat).setHTML(fmt(e.features[0].properties)).addTo(map);});
    map.on('mouseenter',layer,()=>map.getCanvas().style.cursor='pointer');
    map.on('mouseleave',layer,()=>map.getCanvas().style.cursor='');
  }
  bind('patches-fill',p=>`<b>Patch #${p.patch_id}</b><br>${p.area_ha} ha &middot; mean &Delta;NDVI ${p.mean_change}<br>robustness ${p.robustness}`);
  bind('scenes-fill',p=>`<b>${p.id}</b><br>${p.acquired||''}<br>cloud ${p.cloud==null||p.cloud==='null'?'n/a':p.cloud+' %'}`);

  if(CFG.focus && !CFG.autorotate){ map.flyTo({center:CFG.focus.center,zoom:CFG.focus.zoom,duration:2200,essential:true}); }
  if(CFG.autorotate){ spinning=true; spin();
    setTimeout(()=>{ if(!userTouched){ focusAoi(); } },3800);
  }
});
})();
</script></body></html>"""


def build_html(aoi_feature: dict, *, basemap: str, overlay: dict | None = None, info: str = "", legend: str = "",
               patches: dict | None = None, scenes: dict | None = None, highlight_patch: int | None = None,
               highlight_scene: str | None = None, focus: dict | None = None, autorotate: bool = True, restore: bool = False,
               opacity: int = 85, zoom: float = 10.6) -> str:
    """Return a self-contained HTML document. Deterministic for equal inputs, so Streamlit only
    reloads the iframe when something visible actually changed."""
    cfg = {"aoi": aoi_feature, "center": [C.CENTER_LON, C.CENTER_LAT], "zoom": zoom, "basemap": BASEMAPS[basemap],
           "overlay": overlay, "info": info, "legend": legend, "patches": patches, "scenes": scenes,
           "highlight_patch": highlight_patch, "highlight_scene": highlight_scene, "focus": focus,
           "autorotate": autorotate, "restore": restore, "opacity": opacity}
    payload = json.dumps(cfg, separators=(",", ":")).replace("</", "<\\/")
    return (_TEMPLATE.replace("__CDN__", CDN).replace("__CONFIG__", payload).replace("__OPACITY__", str(opacity)))


def overlay_coords(bounds: tuple[float, float, float, float]) -> list[list[float]]:
    w, s, e, n = bounds
    return [[w, n], [e, n], [e, s], [w, s]]  # TL, TR, BR, BL
