from typing import List, Optional

from .model import AccentPhrase, Mora, ParseKanaError, ParseKanaErrorCode
from .mora_list import openjtalk_mora2text, openjtalk_text2mora

LOOP_LIMIT = 300
UNVOICE_SYMBOL = "_"
ACCENT_SYMBOL = "'"
NOPAUSE_DELIMITER = "/"
PAUSE_DELIMITER = "、"
WIDE_INTERROGATION_MARK = "？"

text2mora_with_unvoice = {}
for text, (consonant, vowel) in openjtalk_text2mora.items():
    text2mora_with_unvoice[text] = Mora(
        text=text,
        consonant=consonant if len(consonant) > 0 else None,
        consonant_length=0 if len(consonant) > 0 else None,
        vowel=vowel,
        vowel_length=0,
        pitch=0,
        is_interrogative=False,
    )
    if vowel in ["a", "i", "u", "e", "o"]:
        text2mora_with_unvoice[UNVOICE_SYMBOL + text] = Mora(
            text=text,
            consonant=consonant if len(consonant) > 0 else None,
            consonant_length=0 if len(consonant) > 0 else None,
            vowel=vowel.upper(),
            vowel_length=0,
            pitch=0,
            is_interrogative=False,
        )


def _text_to_accent_phrase(phrase: str) -> List[AccentPhrase]:
    """
    longest matchにより読み仮名からAccentPhraseを生成
    入力長Nに対し計算量O(N^2)
    """
    accent_index: Optional[int] = None
    moras: List[Mora] = []

    base_index = 0  # パース開始位置。ここから右の文字列をstackに詰めていく。
    stack = ""  # 保留中の文字列
    matched_text: Optional[str] = None  # 保留中の文字列内で最後にマッチした仮名

    outer_loop = 0
    while base_index < len(phrase):
        outer_loop += 1
        if phrase[base_index] == ACCENT_SYMBOL:
            if len(moras) == 0:
                raise ParseKanaError(ParseKanaErrorCode.ACCENT_TOP, text=phrase)
            if accent_index is not None:
                raise ParseKanaError(ParseKanaErrorCode.ACCENT_TWICE, text=phrase)
            accent_index = len(moras)
            base_index += 1
            continue
        for watch_index in range(base_index, len(phrase)):
            if phrase[watch_index] == ACCENT_SYMBOL:
                break
            # 普通の文字の場合
            stack += phrase[watch_index]
            if stack in text2mora_with_unvoice:
                matched_text = stack
        # push mora
        if matched_text is None:
            raise ParseKanaError(ParseKanaErrorCode.UNKNOWN_TEXT, text=stack)
        else:
            moras.append(text2mora_with_unvoice[matched_text])
            base_index += len(matched_text)
            stack = ""
            matched_text = None
        if outer_loop > LOOP_LIMIT:
            raise ParseKanaError(ParseKanaErrorCode.INFINITE_LOOP)
    if accent_index is None:
        raise ParseKanaError(ParseKanaErrorCode.ACCENT_NOTFOUND, text=phrase)
    else:
        return AccentPhrase(moras=moras, accent=accent_index, pause_mora=None)


def parse_kana(text: str, enable_interrogative: bool) -> List[AccentPhrase]:
    """
    AquesTalkライクな読み仮名をパースして音長・音高未指定のaccent phraseに変換
    """
    parsed_results: List[AccentPhrase] = []
    phrase_base = 0
    if len(text) == 0:
        raise ParseKanaError(ParseKanaErrorCode.EMPTY_PHRASE, position=1)
    is_interrogative_text = text[-1] == WIDE_INTERROGATION_MARK
    if is_interrogative_text:
        text = text[:-1]

    for i in range(len(text) + 1):
        if i == len(text) or text[i] in [PAUSE_DELIMITER, NOPAUSE_DELIMITER]:
            phrase = text[phrase_base:i]
            if len(phrase) == 0:
                raise ParseKanaError(
                    ParseKanaErrorCode.EMPTY_PHRASE,
                    position=str(len(parsed_results) + 1),
                )
            phrase_base = i + 1
            accent_phrase: AccentPhrase = _text_to_accent_phrase(phrase)
            if i < len(text) and text[i] == PAUSE_DELIMITER:
                accent_phrase.pause_mora = Mora(
                    text="、",
                    consonant=None,
                    consonant_length=None,
                    vowel="pau",
                    vowel_length=0,
                    pitch=0,
                )
            parsed_results.append(accent_phrase)

    if enable_interrogative and is_interrogative_text:
        last_parsed_result = parsed_results[-1]
        last_mora = last_parsed_result.moras[-1]
        last_parsed_result.moras.append(
            Mora(
                text=openjtalk_mora2text[last_mora.vowel],
                consonant=None,
                consonant_length=None,
                vowel=last_mora.vowel,
                vowel_length=last_mora.vowel_length,
                pitch=0,
            )
        )
        last_parsed_result.is_interrogative = True

    return parsed_results


def create_kana(accent_phrases: List[AccentPhrase]) -> str:
    text = ""
    replace_vowel_to_interrogative = (
        len(accent_phrases) > 0
        and accent_phrases[-1].is_interrogative
        and len(accent_phrases[-1].moras) > 0
        and accent_phrases[-1].moras[-1].pitch > 0
    )
    for i, phrase in enumerate(accent_phrases):
        for j, mora in enumerate(phrase.moras):
            if mora.vowel in ["A", "I", "U", "E", "O"]:
                text += UNVOICE_SYMBOL

            # TODO: 疑問系が正式に対応したらここの処理をmora.textを追加した上で疑問符を追加する処理に変更する
            if (
                replace_vowel_to_interrogative
                and i == len(accent_phrases) - 1
                and j == len(phrase.moras) - 1
            ):
                text += WIDE_INTERROGATION_MARK
            else:
                text += mora.text
            if j + 1 == phrase.accent:
                text += ACCENT_SYMBOL
        if i < len(accent_phrases) - 1:
            if phrase.pause_mora is None:
                text += NOPAUSE_DELIMITER
            else:
                text += PAUSE_DELIMITER
    return text
