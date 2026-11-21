"use client";
import { ExternalLink, ShieldCheck } from "lucide-react";
export type TafsirSource={
  source_id:string;author:string;title:string;verse:string;
  url:string;provenance:string;edition_verified:boolean;
};
export function SourcePills({sources,needsReview=false}:{sources:TafsirSource[];needsReview?:boolean}){
  if(!sources.length)return <p className="mt-5 text-xs text-[#E6D5B8]">Classical source transcriptions are currently unavailable. No source citation will be invented.</p>;
  return <section className="mt-6 border-t border-[#4A3828] pt-4">
    <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#E6D5B8]">
      <ShieldCheck size={16} className="text-[#C8A96E]"/> Classical sources
    </h3>
    <div className="flex flex-wrap gap-2">
      {sources.map(source=>{
        let address:URL;
        try{address=new URL(source.url)}catch{return null}
        if(address.protocol!=="https:")return null;
        return <a key={source.source_id} target="_blank" rel="noopener noreferrer" href={address.href}
          className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[#C8A96E]/30 bg-[#2A1F18] px-4 py-2 text-xs text-[#EDD39F]">
          {source.author} <ExternalLink size={13}/>
        </a>;
      })}
    </div>
    <p className="mt-3 text-xs leading-relaxed text-[#C0AB90]">
      {needsReview?
        "These links identify retrieved classical transcriptions; AI summaries and attributions may still require scholarly review.":
        "These are linked source transcriptions, not certified manuscript-critical editions."}
    </p>
  </section>;
}
