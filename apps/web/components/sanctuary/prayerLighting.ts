/** City-selected prayer-time ambience; do not use as a fiqh timetable.
 * Calculated times depend on local method and community timetable.
 */
import { Coordinates, CalculationMethod, PrayerTimes } from "adhan";
import type { RoomLighting } from "./WindowLoungeScene";
export const CITY_OPTIONS = {
  london:{label:"London, UK",lat:51.5074,lng:-.1278,timeZone:"Europe/London"},
  riyadh:{label:"Riyadh, Saudi Arabia",lat:24.7136,lng:46.6753,timeZone:"Asia/Riyadh"},
  doha:{label:"Doha, Qatar",lat:25.2854,lng:51.5310,timeZone:"Asia/Qatar"},
  makkah:{label:"Makkah, Saudi Arabia",lat:21.3891,lng:39.8579,timeZone:"Asia/Riyadh"},
  islamabad:{label:"Islamabad, Pakistan",lat:33.6844,lng:73.0479,timeZone:"Asia/Karachi"},
  jakarta:{label:"Jakarta, Indonesia",lat:-6.2088,lng:106.8456,timeZone:"Asia/Jakarta"},
} as const;
export type CityId=keyof typeof CITY_OPTIONS;
export function sceneLightingFromPrayerPeriods(city:CityId,now=new Date()):Exclude<RoomLighting,"auto">{
 const info=CITY_OPTIONS[city];
 const coordinates=new Coordinates(info.lat,info.lng);
 const params=CalculationMethod.MuslimWorldLeague();
 const prayers=new PrayerTimes(coordinates,now,params);
 const moment=now.getTime();
 if(moment>=prayers.fajr.getTime()&&moment<prayers.sunrise.getTime())return "fajr";
 if(moment>=prayers.asr.getTime()&&moment<prayers.maghrib.getTime())return "asr";
 if(moment>=prayers.isha.getTime()||moment<prayers.fajr.getTime())return "isha";
 // The three artistic lighting presets intentionally group Dhuhr with warm day.
 return "asr";
}
