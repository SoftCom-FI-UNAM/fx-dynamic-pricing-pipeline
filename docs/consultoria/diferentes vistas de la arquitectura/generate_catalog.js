// Genera un catálogo de productos ficticio para simular el export periódico de SQL Server.
// Sin dependencias. RNG LCG con semilla fija para reproducibilidad.
const fs = require('node:fs');
const path = require('node:path');

const SEED = 20261112;
const ROWS = 100;
const output = process.argv[2] || path.join(__dirname, '..', 'data', 'catalogo_sqlserver_sintetico.csv');
let state = SEED >>> 0;

function random() {
  state = (Math.imul(1664525, state) + 1013904223) >>> 0;
  return state / 0x100000000;
}
function between(min, max, decimals = 2) {
  return Number((min + random() * (max - min)).toFixed(decimals));
}
function money(value) {
  return value.toFixed(2);
}

const categories = ['electrónica', 'hogar', 'deportes', 'moda', 'cuidado_personal'];
const header = [
  'product_id', 'sku', 'category', 'base_price_usd', 'unit_cost_usd',
  'fx_mxn_per_usd', 'margin_floor_pct', 'promo_discount_pct', 'recommended_price_mxn'
];
const lines = [header.join(',')];

for (let i = 1; i <= ROWS; i++) {
  const basePrice = between(8, 850);
  const unitCost = between(basePrice * 0.35, basePrice * 0.78);
  const fx = between(16.5, 21.5, 4);
  const marginFloor = between(0.18, 0.35, 4);
  const promoDiscount = between(0, 0.20, 4);
  const promotionalPrice = basePrice * fx * (1 - promoDiscount);
  const minimumMarginPrice = unitCost * fx / (1 - marginFloor);
  const recommendedPrice = Math.max(promotionalPrice, minimumMarginPrice);
  const row = [
    `P${String(i).padStart(4, '0')}`,
    `SKU-${String(i).padStart(4, '0')}`,
    categories[(i - 1) % categories.length],
    money(basePrice), money(unitCost), fx.toFixed(4),
    marginFloor.toFixed(4), promoDiscount.toFixed(4), money(recommendedPrice)
  ];
  lines.push(row.join(','));
}

const fullPath = path.resolve(output);
fs.mkdirSync(path.dirname(fullPath), { recursive: true });
fs.writeFileSync(fullPath, `${lines.join('\n')}\n`, 'utf8');
console.log(`Escritos ${ROWS} productos en ${fullPath} (semilla ${SEED}).`);

