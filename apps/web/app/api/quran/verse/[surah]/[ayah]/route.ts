import { AYAHS_PER_SURAH, audioUrl, RECITERS, validVerse, type ReciterId } from "@/lib/quranMetadata";

import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import path from "node:path";

let corpus: string[] | undefined;

async function bundledAyah(surah:number, ayah:number) {
  if (!corpus) {
    const file = await readFile(path.join(process.cwd(), "data", "tanzil-uthmani.txt.gz"));
    const lines = gunzipSync(file).toString("utf8").split(/\r?\n/).filter(line=>line && !line.startsWith("#"));
    if (lines.length !== 6236) throw Error("Invalid bundled corpus");
    corpus = lines;
  }
  const offset = AYAHS_PER_SURAH.slice(1,surah).reduce<number>((sum,n)=>sum+n,0);
  return corpus[offset+ayah-1];
}

type SourceWord = {
  position: number;
  char_type_name: string;
  text_uthmani: string;
  translation?: { text?: string };
  transliteration?: { text?: string };
};

function plain(text = "") {
  return text.replace(/<sup\b[^>]*>[\s\S]*?<\/sup>/gi, "").replace(/<[^>]+>/g, "").trim();
}

export async function GET(request: Request, context: {params: Promise<{surah:string; ayah:string}>}) {
  const params = await context.params;
  const surah = Number(params.surah), ayah = Number(params.ayah);
  const query = new URL(request.url).searchParams;
  const reciter = query.get("reciter") ?? "dosari";
  if (!validVerse(surah, ayah)) return Response.json({detail:"Invalid verse"}, {status:404});
  if (!Object.hasOwn(RECITERS, reciter) || (query.get("lang") ?? "en") !== "en") {
    return Response.json({detail:"Unsupported reader selection"}, {status:422});
  }
  const key = `${surah}:${ayah}`;
  const source = new URL(`https://api.quran.com/api/v4/verses/by_key/${key}`);
  source.search = new URLSearchParams({
    words:"true", word_fields:"text_uthmani", fields:"text_uthmani", translations:"131", language:"en",
  }).toString();
  try {
    const response = await fetch(source, {next:{revalidate:86400}, signal:AbortSignal.timeout(4000)});
    if (!response.ok) throw Error();
    const {verse} = await response.json();
    if (verse?.verse_key !== key || !verse.text_uthmani || !Array.isArray(verse.words)) throw Error();
    const words = (verse.words as SourceWord[]).filter(word=>word.char_type_name==="word");
    if (!words.length || words.some((word,i)=>word.position!==i+1 || !word.text_uthmani)) throw Error();
    const translation = plain(verse.translations?.find((t:{resource_id:number})=>t.resource_id===131)?.text);

    return Response.json({
      surah, ayah, arabic_uthmani:verse.text_uthmani, translation,
      translation_attribution:translation ? "Quran Foundation translation resource 131" : "",
      words:words.map(w=>({id:`${key}:${w.position}`, index:w.position, arabic:w.text_uthmani,
        meaning:plain(w.translation?.text), transliteration:plain(w.transliteration?.text)||null})),
      audio_url:audioUrl(surah,ayah,reciter as ReciterId), reciter:RECITERS[reciter as ReciterId].label,
      free:true,
    }, {headers:{"Cache-Control":"public, s-maxage=86400, stale-while-revalidate=86400"}});
  } catch {
    return Response.json({surah, ayah, arabic_uthmani:await bundledAyah(surah,ayah), words:[],
      translation:"", translation_attribution:"", text_source:"Tanzil", free:true,
      audio_url:audioUrl(surah,ayah,reciter as ReciterId), reciter:RECITERS[reciter as ReciterId].label,
    });

  }
}
