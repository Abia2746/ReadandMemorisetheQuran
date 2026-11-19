# Attribution and licence for source-matched word timing data

These `quranlife_*.json` files are transformed excerpts of the source timing datasets published by **QuranLife App** at:

https://github.com/QuranLife/TimingFilesCode

Upstream source files:
- `timing_files/Yasser_Ad-Dussary_128kbps.json`
- `timing_files/Mishary_Alafasy_64kbps.json`

**Licence: Creative Commons Attribution 4.0 International (CC BY 4.0).**
https://creativecommons.org/licenses/by/4.0/

**Transformation:** the upstream verse rows were grouped into files for blocks of 20 surahs. The zero-based and one-based sequential word index columns were omitted, retaining start and end offsets in milliseconds for each word, in their original order. No independent correction or human audition of these automatically generated timestamps has been performed. The display only uses a row if its word count matches Quran.com data and its offsets are valid.

**Audio sources:** recordings from [EveryAyah](https://everyayah.com/), using exactly the folders named above. This attribution does not imply endorsement by QuranLife or EveryAyah.

The source project's own README warns that timing files are a work in progress and that short words, repetitions and long verses can produce alignment errors. The application therefore labels these as **automatically generated, source-matched timings**, not certified exact alignments. For missing or rejected rows it highlights the ayah instead of inventing a word timing.

The audio itself is not included in these files.
