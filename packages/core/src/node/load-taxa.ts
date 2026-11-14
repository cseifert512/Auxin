/**
 * Node-only: read the taxon library from the `species/` folder.
 * Browser builds receive the same JSON through their bundler instead.
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { type Morphology, parseMorphology } from '../morphology.ts';
import { type BandEnd, type GrowthModel, atBandEnd, parseGrowthModel } from '../sim/model.ts';
import { type TaxonProfile, parseTaxon } from '../taxon.ts';

export function loadTaxa(speciesDir: string): Map<string, TaxonProfile> {
  const out = new Map<string, TaxonProfile>();
  for (const name of readdirSync(speciesDir).sort()) {
    const dir = join(speciesDir, name);
    if (!statSync(dir).isDirectory()) continue;
    const file = join(dir, 'taxon.json');
    const taxon = parseTaxon(JSON.parse(readFileSync(file, 'utf8')), file);
    if (taxon.id !== name) throw new Error(`${file}: id "${taxon.id}" does not match its folder "${name}"`);
    out.set(taxon.id, taxon);
  }
  return out;
}

/** The growth models that exist so far: one `model.json` beside a taxon's profile. */
export function loadGrowthModels(speciesDir: string): Map<string, GrowthModel> {
  const out = new Map<string, GrowthModel>();
  for (const name of readdirSync(speciesDir).sort()) {
    const file = join(speciesDir, name, 'model.json');
    if (!existsSync(file)) continue;
    const model = parseGrowthModel(JSON.parse(readFileSync(file, 'utf8')), file);
    if (model.taxonId !== name) throw new Error(`${file}: taxonId "${model.taxonId}" does not match its folder "${name}"`);
    out.set(name, model);
  }
  return out;
}

/** The morphology files that exist so far: one `morphology.json` beside a taxon's profile. */
export function loadMorphologies(speciesDir: string): Map<string, Morphology> {
  const out = new Map<string, Morphology>();
  for (const name of readdirSync(speciesDir).sort()) {
    const file = join(speciesDir, name, 'morphology.json');
    if (!existsSync(file)) continue;
    const morphology = parseMorphology(JSON.parse(readFileSync(file, 'utf8')), file);
    if (morphology.taxonId !== name) throw new Error(`${file}: taxonId "${morphology.taxonId}" does not match its folder "${name}"`);
    out.set(name, morphology);
  }
  return out;
}

/**
 * Which end of their extension ranges the growth models are to be run at, where the environment says:
 * `HORTI_GROWTH_BAND=low` or `high`. For a caller that loads the library and cannot be given an option, such as
 * a script in another repository. Anything else, or nothing: the models as they are written.
 */
export function bandFromEnvironment(): BandEnd | null {
  const end = process.env.HORTI_GROWTH_BAND;
  if (end === undefined || end === '') return null;
  if (end !== 'low' && end !== 'high') throw new Error(`HORTI_GROWTH_BAND is "${end}": it is "low" or "high", or not set`);
  return end;
}

/**
 * Taxa that can be grown: those with both a profile and a growth model.
 *
 * `band`: every model taken to the low or the high end of the ranges it gives for extension (`atBandEnd`), so that
 * a result can be given as a band. Left out, the environment is asked (`bandFromEnvironment`); null, the models as
 * written whatever the environment says. Each parameter changed is labelled a variation, and a run's design report
 * lists it, so a run made at one end says so itself.
 */
export function loadGrowable(speciesDir: string, options: { band?: BandEnd | null } = {}): Map<string, { profile: TaxonProfile; model: GrowthModel }> {
  const band = options.band === undefined ? bandFromEnvironment() : options.band;
  const taxa = loadTaxa(speciesDir);
  const out = new Map<string, { profile: TaxonProfile; model: GrowthModel }>();
  for (const [id, model] of loadGrowthModels(speciesDir)) out.set(id, { profile: taxa.get(id)!, model: band ? atBandEnd(model, band) : model });
  return out;
}
