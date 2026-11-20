import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const AlMuallimApp());

class QuranWord {
  final String arabic;
  final String translation;
  final int position;
  const QuranWord(this.arabic, this.translation, this.position);
}

class QuranVerse {
  final int number;
  final List<QuranWord> words;
  const QuranVerse(this.number, this.words);
}

class QuranService {
  static Future<List<QuranVerse>> fetchVerses(int surah) async {
    final uri = Uri.https('api.quran.com', '/api/v4/verses/by_chapter/$surah', {
      'language': 'en',
      'words': 'true',
      'word_fields': 'text_uthmani,translation',
      'per_page': '50',
      'page': '1',
    });
    final response = await http.get(uri).timeout(const Duration(seconds: 18));
    if (response.statusCode != 200) throw Exception('Qur’an service unavailable');
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final verses = (data['verses'] as List<dynamic>? ?? []);
    return verses.map((raw) {
      final v = raw as Map<String, dynamic>;
      final words = (v['words'] as List<dynamic>? ?? []).cast<Map<String, dynamic>>()
          .where((w) => w['char_type_name'] == 'word')
          .map((w) => QuranWord(
                (w['text_uthmani'] ?? '').toString(),
                ((w['translation'] as Map?)?['text'] ?? '').toString(),
                (w['position'] as num?)?.toInt() ?? 0,
              )).toList();
      return QuranVerse((v['verse_number'] as num?)?.toInt() ?? 0, words);
    }).toList();
  }
}

enum ReaderMode { read, memorise, listen }

class AlMuallimApp extends StatelessWidget {
  const AlMuallimApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Al-Mu’allim',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: const Color(0xFFF8F5ED),
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF607F70),
        primary: const Color(0xFF45695B),
        surface: const Color(0xFFF8F5ED),
      ),
    ),
    home: const ReaderScreen(),
  );
}

class ReaderScreen extends StatefulWidget {
  const ReaderScreen({super.key});
  @override
  State<ReaderScreen> createState() => _ReaderScreenState();
}

class _ReaderScreenState extends State<ReaderScreen> {
  ReaderMode mode = ReaderMode.read;
  int surah = 1;
  late Future<List<QuranVerse>> verses;
  final Set<String> revealed = {};
  final Set<String> difficult = {};
  String? selected;

  @override
  void initState() {
    super.initState();
    verses = QuranService.fetchVerses(surah);
    _restore();
  }

  Future<void> _restore() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      surah = prefs.getInt('surah') ?? 1;
      mode = ReaderMode.values[(prefs.getInt('mode') ?? 0).clamp(0, 2)];
      difficult.addAll(prefs.getStringList('difficult') ?? []);
      verses = QuranService.fetchVerses(surah);
    });
  }

  Future<void> _save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('surah', surah);
    await prefs.setInt('mode', mode.index);
    await prefs.setStringList('difficult', difficult.toList());
  }

  void _selectSurah(int value) {
    setState(() {
      surah = value;
      selected = null;
      revealed.clear();
      verses = QuranService.fetchVerses(surah);
    });
    _save();
  }

  void _selectWord(String key) {
    setState(() {
      selected = key;
      if (mode == ReaderMode.memorise) revealed.add(key);
    });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      backgroundColor: const Color(0xFFF8F5ED),
      title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('AL-MU’ALLIM', style: TextStyle(fontWeight: FontWeight.w700, letterSpacing: 2, fontSize: 18)),
        Text('QUR’AN STUDIO', style: TextStyle(fontSize: 10, letterSpacing: 3)),
      ]),
      actions: [
        IconButton(
          tooltip: 'Refresh Qur’an text',
          onPressed: () => setState(() => verses = QuranService.fetchVerses(surah)),
          icon: const Icon(Icons.refresh_rounded),
        ),
      ],
    ),
    body: SafeArea(
      child: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 10, 18, 8),
          child: Column(children: [
            Text('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ',
                textDirection: TextDirection.rtl,
                style: const TextStyle(fontSize: 25, color: Color(0xFF45695B), height: 2)),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Text('Surah  ', style: TextStyle(fontSize: 13)),
              DropdownButton<int>(
                value: surah,
                items: List.generate(114, (i) => DropdownMenuItem(value: i + 1, child: Text('${i + 1}'))),
                onChanged: (v) { if (v != null) _selectSurah(v); },
              ),
            ]),
            const SizedBox(height: 8),
            SegmentedButton<ReaderMode>(
              showSelectedIcon: false,
              segments: const [
                ButtonSegment(value: ReaderMode.read, label: Text('Read'), icon: Icon(Icons.menu_book_outlined)),
                ButtonSegment(value: ReaderMode.memorise, label: Text('Memorise'), icon: Icon(Icons.psychology_alt_outlined)),
                ButtonSegment(value: ReaderMode.listen, label: Text('Listen'), icon: Icon(Icons.headphones_outlined)),
              ],
              selected: {mode},
              onSelectionChanged: (m) { setState(() => mode = m.first); _save(); },
            ),
          ]),
        ),
        Expanded(child: FutureBuilder<List<QuranVerse>>(
          future: verses,
          builder: (context, snapshot) {
            if (snapshot.hasError) return Center(child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Text('Could not load Qur’an text. Check your connection.'),
                const SizedBox(height: 12),
                FilledButton(onPressed: () => setState(() => verses = QuranService.fetchVerses(surah)), child: const Text('Retry')),
              ]),
            ));
            if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
            final data = snapshot.data!;
            if (data.isEmpty) return const Center(child: Text('No verses returned.'));
            return ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              itemCount: data.length,
              itemBuilder: (context, i) {
                final verse = data[i];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 26),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Wrap(
                      alignment: WrapAlignment.center,
                      textDirection: TextDirection.rtl,
                      spacing: 7,
                      runSpacing: 14,
                      children: [
                        for (final word in verse.words)
                          Builder(builder: (context) {
                            final key = '$surah:${verse.number}:${word.position}';
                            final isSelected = selected == key;
                            final hidden = mode == ReaderMode.memorise && !revealed.contains(key);
                            return InkWell(
                              borderRadius: BorderRadius.circular(8),
                              onTap: () => _selectWord(key),
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 130),
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 5),
                                decoration: BoxDecoration(
                                  color: isSelected ? const Color(0xFFE7D8A9) : Colors.transparent,
                                  borderRadius: BorderRadius.circular(8),
                                  border: difficult.contains(key) ? Border.all(color: const Color(0xFFB58A4A)) : null,
                                ),
                                child: Text(hidden ? '•••' : word.arabic,
                                  textDirection: TextDirection.rtl,
                                  style: const TextStyle(fontSize: 29, height: 1.8, color: Color(0xFF283D34))),
                              ),
                            );
                          }),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text('۞  ${verse.number}', textAlign: TextAlign.center,
                      style: const TextStyle(color: Color(0xFFB58A4A), fontSize: 17)),
                  ]),
                );
              },
            );
          },
        )),
        if (selected != null) Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(18, 10, 18, 14),
          decoration: const BoxDecoration(
            color: Color(0xFFEDE9DD),
            border: Border(top: BorderSide(color: Color(0xFFD4C8AC))),
          ),
          child: Wrap(alignment: WrapAlignment.center, spacing: 8, children: [
            OutlinedButton.icon(
              onPressed: () {
                setState(() {
                  if (difficult.contains(selected)) { difficult.remove(selected); }
                  else { difficult.add(selected!); }
                });
                _save();
              },
              icon: const Icon(Icons.flag_outlined),
              label: Text(difficult.contains(selected) ? 'Remove flag' : 'Flag for review'),
            ),
            if (mode == ReaderMode.memorise)
              OutlinedButton(
                onPressed: () => setState(() => revealed.remove(selected)),
                child: const Text('Hide again'),
              ),
          ]),
        ),
        if (mode == ReaderMode.listen)
          const Padding(
            padding: EdgeInsets.all(12),
            child: Text('Reciter playback will be connected in the next milestone.'),
          ),
      ]),
    ),
  );
}
