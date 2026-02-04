# lemmatizer.py
import logging
import re
from typing import Optional, List

logger = logging.getLogger(__name__)


class QueryLemmatizer:
    """Класс для лемматизации пользовательского запроса"""

    def __init__(self):
        self.morph = None
        # Список стоп-слов
        self.stop_words = set([
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то',
            'все', 'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за',
            'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет',
            'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если',
            'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять',
            'уж', 'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они',
            'тут', 'где', 'есть', 'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была',
            'сам', 'чтоб', 'без', 'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет',
            'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого', 'какой', 'совсем',
            'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас',
            'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два',
            'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас',
            'про', 'всего', 'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем',
            'хорошо', 'свою', 'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя',
            'такой', 'им', 'более', 'всегда', 'конечно', 'всю', 'между'
        ])

        self._init_morph()

    def _init_morph(self):
        """Инициализирует морфологический анализатор"""
        # Сначала пытаемся использовать pymorphy3 (совместим с Python 3.11+)
        try:
            import pymorphy3
            self.morph = pymorphy3.MorphAnalyzer()
            logger.info("Лемматизатор инициализирован успешно (pymorphy3)")
            return
        except ImportError as e:
            logger.debug(f"pymorphy3 не установлен: {e}")

        # Затем пытаемся использовать pymorphy2 (для старых версий Python)
        try:
            import pymorphy2
            self.morph = pymorphy2.MorphAnalyzer()
            logger.info("Лемматизатор инициализирован успешно (pymorphy2)")
        except ImportError as e:
            logger.warning(f"pymorphy2 не установлен: {e}")
            logger.warning("Установите pymorphy3 для Python 3.11+: pip install pymorphy3")
            logger.warning(
                "Или установите pymorphy2 для старых версий Python: pip install pymorphy2 pymorphy2-dicts-ru")
            self.morph = None
        except AttributeError as e:
            # Ошибка совместимости pymorphy2 с Python 3.11+
            if "has no attribute 'getargspec'" in str(e):
                logger.error("pymorphy2 несовместим с этой версией Python")
                logger.error("Установите pymorphy3: pip install pymorphy3")
                self.morph = None
            else:
                logger.error(f"Ошибка инициализации pymorphy2: {e}")
                self.morph = None
        except Exception as e:
            logger.error(f"Ошибка инициализации лемматизатора: {e}")
            self.morph = None

    def lemmatize_query(self, query: str) -> str:
        """Лемматизирует запрос пользователя"""
        if not query or not isinstance(query, str):
            logger.warning(f"Некорректный запрос: {query}")
            return query

        if not self.morph:
            logger.debug("Лемматизатор недоступен, возвращаем исходный запрос")
            return query

        try:
            # Очистка запроса: удаляем знаки препинания, приводим к нижнему регистру
            query_clean = re.sub(r'[^\w\s]', ' ', query.lower())
            # Удаляем лишние пробелы
            query_clean = re.sub(r'\s+', ' ', query_clean).strip()

            if not query_clean:
                logger.debug("Запрос пуст после очистки")
                return query

            words = query_clean.split()
            lemmas = []

            for word in words:
                if not word or word in self.stop_words:
                    continue

                try:
                    # Получаем нормальную форму слова
                    parsed = self.morph.parse(word)[0]
                    lemma = parsed.normal_form
                    lemmas.append(lemma)
                except Exception as e:
                    logger.debug(f"Ошибка лемматизации слова '{word}': {e}")
                    # Если не получилось лемматизировать, используем исходное слово
                    lemmas.append(word)

            lemmatized_query = ' '.join(lemmas)

            if lemmatized_query:
                logger.debug(f"Лемматизация: '{query}' -> '{lemmatized_query}'")
                return lemmatized_query
            else:
                logger.debug(f"Запрос после лемматизации пуст: '{query}'")
                return query

        except Exception as e:
            logger.error(f"Критическая ошибка лемматизации: {e}")
            return query

    def is_available(self) -> bool:
        """Проверяет доступность лемматизатора"""
        return self.morph is not None

    def add_stop_words(self, words: List[str]):
        """Добавляет дополнительные стоп-слова"""
        if isinstance(words, list):
            self.stop_words.update(words)
            logger.debug(f"Добавлено {len(words)} стоп-слов")

    def remove_stop_words(self, words: List[str]):
        """Удаляет стоп-слова из списка"""
        removed = 0
        for word in words:
            if word in self.stop_words:
                self.stop_words.remove(word)
                removed += 1
        logger.debug(f"Удалено {removed} стоп-слов")

    def get_stop_words(self) -> List[str]:
        """Возвращает список стоп-слов"""
        return list(self.stop_words)