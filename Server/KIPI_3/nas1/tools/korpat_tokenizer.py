# coding=utf-8
# Copyright 2020 Korea Institute of Patent Information(KIPI) Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unicodedata
import collections
import mecab
import codecs

class Tokenizer(object):

    def __init__(self,
                 vocab_path,
                 token_cls="[CLS]",
                 token_sep="[SEP]",
                 token_unk="[UNK]",
                 pad_index=0,
                 cased=True):
        """Initialize tokenizer.

        :param vocab_path: A vocabulary path for generate token dictionary
        :param token_cls: The token represents classification.
        :param token_sep: The token represents separator.
        :param token_unk: The token represents unknown token.
        :param pad_index: The index to pad.
        :param cased: Whether to keep the case. If Korean, True
        """
        # token dictionay 생성
        token_dict = {}
        with codecs.open(vocab_path, 'r', 'utf8') as reader:
            for line in reader:
                token = line.strip()
                token_dict[token] = len(token_dict)
        
        self._token_dict = token_dict
        self._token_dict_inv = {v: k for k, v in token_dict.items()}
        self._token_cls = token_cls
        self._token_sep = token_sep
        self._token_unk = token_unk
        self._pad_index = pad_index
        self._cased = cased
        
        # Mecab 형태소분석기 사용
        self._mecab = mecab.MeCab()

        # TODO : SNU Bidirectional Word Piece 적용
        self.rev_unk_token = "]KNU["
        self.rev_token_dict = collections.OrderedDict({''.join(reversed(k)): v for k, v in token_dict.items()})

    @staticmethod
    def _truncate(first_tokens, second_tokens=None, max_len=None):
        if max_len is None:
            return

        if second_tokens is not None:
            while True:
                total_len = len(first_tokens) + len(second_tokens)
                if total_len <= max_len - 3:  # 3 for [CLS] .. tokens_a .. [SEP] .. tokens_b [SEP]
                    break
                if len(first_tokens) > len(second_tokens):
                    first_tokens.pop()
                else:
                    second_tokens.pop()
        else:
            del first_tokens[max_len - 2:]  # 2 for [CLS] .. tokens .. [SEP]

    def _pack(self, first_tokens, second_tokens=None):
        first_packed_tokens = [self._token_cls] + first_tokens + [self._token_sep]
        if second_tokens is not None:
            second_packed_tokens = second_tokens + [self._token_sep]
            return first_packed_tokens + second_packed_tokens, len(first_packed_tokens), len(second_packed_tokens)
        else:
            return first_packed_tokens, len(first_packed_tokens), 0

    def _convert_tokens_to_ids(self, tokens):
        unk_id = self._token_dict.get(self._token_unk)
        return [self._token_dict.get(token, unk_id) for token in tokens]
    
    def _convert_ids_to_tokens(self, ids):
    # unk_id = self._token_dict.get(self._token_unk)
        return [self._token_dict_inv.get(id, self._token_unk) for id in ids]

    def tokenize(self, first, second=None):
        """Split text to tokens.

        :param first: First text.
        :param second: Second text.
        :return: A list of strings.
        """
        # Mecab Pre Tokenize
        first = " ".join(self._mecab.morphs(first)).strip()
        second = " ".join(self._mecab.morphs(second)).strip() if second is not None else None

        # SentencePiece Post Tokenize
        first_tokens = self._tokenize(first)
        second_tokens = self._tokenize(second) if second is not None else None
        
        tokens, _, _ = self._pack(first_tokens, second_tokens)
        return tokens

    def encode(self, first, second=None, max_len=None):
        
        # Mecab Pre Tokenize
        try:
            first = " ".join(self._mecab.morphs(first)).strip()
        except:
            first = first
        second = " ".join(self._mecab.morphs(second)).strip() if second is not None else None
        
        # SentencePiece Post Tokenize
        first_tokens = self._tokenize(first)
        second_tokens = self._tokenize(second) if second is not None else None
        self._truncate(first_tokens, second_tokens, max_len)
        tokens, first_len, second_len = self._pack(first_tokens, second_tokens)

        token_ids = self._convert_tokens_to_ids(tokens)
        segment_ids = [0] * first_len + [1] * second_len

        if max_len is not None:
            pad_len = max_len - first_len - second_len
            token_ids += [self._pad_index] * pad_len
            segment_ids += [0] * pad_len

        return token_ids, segment_ids

    def decode(self, ids):
        sep = ids.index(self._token_dict[self._token_sep])
        try:
            stop = ids.index(self._pad_index)
        except ValueError as e:
            stop = len(ids)
        tokens = [self._token_dict_inv[i] for i in ids]
        first = tokens[1:sep]
        if sep < stop - 1:
            second = tokens[sep + 1:stop - 1]
            return first, second
        return first

    def _tokenize(self, text):
        if not self._cased:
            text = unicodedata.normalize('NFD', text)
            text = ''.join([ch for ch in text if unicodedata.category(ch) != 'Mn'])
            text = text.lower()
        spaced = ''
        for ch in text:
            if self._is_punctuation(ch) or self._is_cjk_character(ch):
                spaced += ' ' + ch + ' '
            elif self._is_space(ch):
                spaced += ' '
            elif ord(ch) == 0 or ord(ch) == 0xfffd or self._is_control(ch):
                continue
            else:
                spaced += ch
        tokens = []
        for word in spaced.strip().split():
            # TODO : SNU Bidirectional Word Piece 적용
            # tokens += self._word_piece_tokenize(word)
            t0, i0 = self._word_piece_tokenize(word)
            t1, i1 = self._word_piece_backword_tokenize(word)

            # print("word===>",word)
            # print("wordpiece===>", t0)
            # print("wordpiece_idx===>", i0)
            # print("bidirectwordpiece===>", t1)
            # print("bidirectwordpiece_idx===>", i1)

            i0 = [i for i in i0 if i > 4]
            i1 = [i for i in i1 if i > 4]
            sub_tokens = t0 if sorted(i0) < sorted(i1) else t1
            for sub_token in sub_tokens:
                tokens.append(sub_token)
        return tokens

    def _word_piece_tokenize(self, word):
        if word in self._token_dict:
            return [[word], [self._token_dict[word]]]
        tokens = []
        start, stop = 0, 0

        # print("word===>", word)
        while start < len(word):
            stop = len(word)
            while stop > start:
                sub = word[start:stop]
                # print("subword ===>", sub)
                if start > 0:
                    sub = '##' + sub
                # print("subword ===>", sub)
                if sub in self._token_dict:
                    break
                stop -= 1
            if start == stop:
                stop += 1
            tokens.append(sub)
            start = stop

        # TODO : Bidirectional Word Piece 적용
        output_tokens = []
        for token in tokens:
            if token in self._token_dict:
                output_tokens.append((token, self._token_dict[token]))
            else:
                output_tokens.append((self._token_unk, self._token_dict[self._token_unk]))
        return [[t for t, i in output_tokens], [i for t, i in output_tokens]]

    # TODO : Bidirectional Word Piece 적용
    def _word_piece_backword_tokenize(self, word):
        if word in self._token_dict:
            return [[word], [self._token_dict[word]]]

        word = "".join(list(reversed(word)))
        # print("word===>", word)

        tokens = []
        start, stop = 0, 0
        while start < len(word):
            stop = len(word)
            while stop > start:
                sub = word[start:stop]
                # print("subword ===>", sub)
                # if start > 0:
                if stop < len(word):
                    # sub = '##' + sub
                    sub = sub + '##'
                # print("subword ===>", sub)
                if sub in self.rev_token_dict:
                    break
                stop -= 1
            if start == stop:
                stop += 1
            tokens.append(sub)
            start = stop

        output_tokens = []
        for token in tokens:
            if token in self.rev_token_dict:
                output_tokens.append((token, self.rev_token_dict[token]))
            else:
                output_tokens.append((self.rev_unk_token, self.rev_token_dict[self.rev_unk_token]))
        output_tokens = [(''.join(reversed(t)), i) for t, i in reversed(output_tokens)]
        return [[t for t, i in output_tokens], [i for t, i in output_tokens]]

    @staticmethod
    def _is_punctuation(ch):
        code = ord(ch)
        return 33 <= code <= 47 or \
            58 <= code <= 64 or \
            91 <= code <= 96 or \
            123 <= code <= 126 or \
            unicodedata.category(ch).startswith('P')

    @staticmethod
    def _is_cjk_character(ch):
        code = ord(ch)
        return 0x4E00 <= code <= 0x9FFF or \
            0x3400 <= code <= 0x4DBF or \
            0x20000 <= code <= 0x2A6DF or \
            0x2A700 <= code <= 0x2B73F or \
            0x2B740 <= code <= 0x2B81F or \
            0x2B820 <= code <= 0x2CEAF or \
            0xF900 <= code <= 0xFAFF or \
            0x2F800 <= code <= 0x2FA1F

    @staticmethod
    def _is_space(ch):
        return ch == ' ' or ch == '\n' or ch == '\r' or ch == '\t' or \
            unicodedata.category(ch) == 'Zs'

    @staticmethod
    def _is_control(ch):
        return unicodedata.category(ch) in ('Cc', 'Cf')

    @staticmethod
    def rematch(text, tokens, cased=False, unknown_token="[UNK]"):
        """Try to find the indices of tokens in the original text.

        >>> Tokenizer.rematch("All rights reserved.", ["all", "rights", "re", "##ser", "##ved", "."])
        [(0, 3), (4, 10), (11, 13), (13, 16), (16, 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.", ["all", "rights", "re", "##ser", "[UNK]", "."])
        [(0, 3), (4, 10), (11, 13), (13, 16), (16, 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.", ["[UNK]", "rights", "[UNK]", "##ser", "[UNK]", "[UNK]"])
        [(0, 3), (4, 10), (11, 13), (13, 16), (16, 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.", ["[UNK]", "righs", "[UNK]", "ser", "[UNK]", "[UNK]"])
        [(0, 3), (4, 10), (11, 13), (13, 16), (16, 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.",
        ...                  ["[UNK]", "rights", "[UNK]", "[UNK]", "[UNK]", "[UNK]"])  # doctest:+ELLIPSIS
        [(0, 3), (4, 10), (11, ... 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.", ["all rights", "reserved", "."])
        [(0, 10), (11, 19), (19, 20)]
        >>> Tokenizer.rematch("All rights reserved.", ["all rights", "reserved", "."], cased=True)
        [(0, 10), (11, 19), (19, 20)]
        >>> Tokenizer.rematch("#hash tag ##", ["#", "hash", "tag", "##"])
        [(0, 1), (1, 5), (6, 9), (10, 12)]
        >>> Tokenizer.rematch("嘛呢，吃了吗？", ["[UNK]", "呢", "，", "[UNK]", "了", "吗", "？"])
        [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)]
        >>> Tokenizer.rematch("  吃了吗？    ", ["吃", "了", "吗", "？"])
        [(2, 3), (3, 4), (4, 5), (5, 6)]

        :param text: Original text.
        :param tokens: Decoded list of tokens.
        :param cased: Whether it is cased.
        :param unknown_token: The representation of unknown token.
        :return: A list of tuples represents the start and stop locations in the original text.
        """
        decoded, token_offsets = '', []
        for token in tokens:
            token_offsets.append([len(decoded), 0])
            if token == unknown_token:
                token = '#'
            if not cased:
                token = token.lower()
            if len(token) > 2 and token.startswith('##'):
                token = token[2:]
            elif len(decoded) > 0:
                token = ' ' + token
                token_offsets[-1][0] += 1
            decoded += token
            token_offsets[-1][1] = len(decoded)

        heading = 0
        text = text.rstrip()
        for i in range(len(text)):
            if not Tokenizer._is_space(text[i]):
                break
            heading += 1
        text = text[heading:]
        len_text, len_decode = len(text), len(decoded)
        costs = [[0] * (len_decode + 1) for _ in range(2)]
        paths = [[(-1, -1)] * (len_decode + 1) for _ in range(len_text + 1)]
        curr, prev = 0, 1

        for j in range(len_decode + 1):
            costs[curr][j] = j
        for i in range(1, len_text + 1):
            curr, prev = prev, curr
            costs[curr][0] = i
            ch = text[i - 1]
            if not cased:
                ch = ch.lower()
            for j in range(1, len_decode + 1):
                costs[curr][j] = costs[prev][j - 1]
                paths[i][j] = (i - 1, j - 1)
                if ch != decoded[j - 1]:
                    costs[curr][j] = costs[prev][j - 1]
                    paths[i][j] = (i - 1, j - 1)
                    if costs[prev][j] < costs[curr][j]:
                        costs[curr][j] = costs[prev][j]
                        paths[i][j] = (i - 1, j)
                    if costs[curr][j - 1] < costs[curr][j]:
                        costs[curr][j] = costs[curr][j - 1]
                        paths[i][j] = (i, j - 1)
                    costs[curr][j] += 1

        matches = [0] * (len_decode + 1)
        position = (len_text, len_decode)
        while position != (-1, -1):
            i, j = position
            matches[j] = i
            position = paths[i][j]

        intervals = [[matches[offset[0]], matches[offset[1]]] for offset in token_offsets]
        for i, interval in enumerate(intervals):
            token_a, token_b = text[interval[0]:interval[1]], tokens[i]
            if len(token_b) > 2 and token_b.startswith('##'):
                token_b = token_b[2:]
            if not cased:
                token_a, token_b = token_a.lower(), token_b.lower()
            if token_a == token_b:
                continue
            if i == 0:
                border = 0
            else:
                border = intervals[i - 1][1]
            for j in range(interval[0] - 1, border - 1, -1):
                if Tokenizer._is_space(text[j]):
                    break
                interval[0] -= 1
            if i + 1 == len(intervals):
                border = len_text
            else:
                border = intervals[i + 1][0]
            for j in range(interval[1], border):
                if Tokenizer._is_space(text[j]):
                    break
                interval[1] += 1
        intervals = [(interval[0] + heading, interval[1] + heading) for interval in intervals]
        return intervals

# If main call
if __name__ == '__main__':

    # 한글의 경우 Cased=True, 영문의 경우 Cased=False
    tokenizer = Tokenizer(vocab_path="./korpat_vocab.txt", cased=True)

    example = "본 고안은 주로 일회용 합성세제액을 집어넣어 밀봉하는 세제액포의 내부를 원호상으로 열중착하되 세제액이 배출되는 절단부 쪽으로 내벽을 협소하게 형성하여서 내부에 들어있는 세제액을 잘짜질 수 있도록 하는 합성세제 액포에 관한 것이다."

    tokens = tokenizer.tokenize(example)
    ids, _ = tokenizer.encode(example, max_len=256)
    decoded_tokens = tokenizer.decode(ids)
    
    print("Length of Token dictionary ===>", len(tokenizer._token_dict.keys()))
    print("Input example ===>", example)
    print("Tokenized example ===>", tokens)
    print("Converted example to IDs ===>", ids)
    print("Converted IDs to example ===>", decoded_tokens)