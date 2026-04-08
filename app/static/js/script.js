// Хранилище данных для режима разработчика
const devMessagesStorage = new Map(); // key: messageId, value: devData

// Счетчик для генерации уникальных ID сообщений
let messageCounter = 0;

// Функция для генерации уникального ID
function generateMessageId() {
    return `msg_${Date.now()}_${messageCounter++}`;
}

// Функция для форматирования времени
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('ru-RU', { 
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false 
    });
}

// Вспомогательная функция для экранирования HTML (с защитой от не-строк)
function escapeHtml(str) {
    if (str === undefined || str === null) return '';
    const stringValue = String(str);
    return stringValue
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Функция для проверки, является ли значение JSON-массивом
function isJSONArray(data) {
    if (!data) return false;
    if (Array.isArray(data)) return true;
    if (typeof data === 'string') {
        const trimmed = data.trim();
        if (!trimmed.startsWith('[')) return false;
        try {
            const parsed = JSON.parse(trimmed);
            return Array.isArray(parsed);
        } catch (e) {
            return false;
        }
    }
    return false;
}

// Функция для получения массива из данных
function getJSONArray(data) {
    if (Array.isArray(data)) return data;
    if (typeof data === 'string') {
        try {
            const parsed = JSON.parse(data);
            if (Array.isArray(parsed)) return parsed;
        } catch (e) {}
    }
    return null;
}

// Функция для преобразования массива в красивый список с разделителями
function arrayToFormattedList(jsonArray) {
    if (!jsonArray || jsonArray.length === 0) {
        return '<div class="list-empty">Нет данных для отображения</div>';
    }
    
    let html = '<div class="data-list">';
    
    jsonArray.forEach((item, index) => {
        // Разделитель между элементами (кроме первого)
        if (index > 0) {
            html += '<div class="list-separator">-------------------------------------------------------</div>';
        }
        
        // Обрабатываем каждый элемент
        if (typeof item === 'object' && item !== null) {
            // Если элемент - объект, выводим только его значения (без ключей)
            html += '<div class="list-item object-item">';
            
            // Получаем все значения объекта
            const values = Object.values(item);
            values.forEach(value => {
                const displayValue = (value === undefined || value === null) ? '' : String(value);
                if (displayValue) {
                    html += `<div class="list-value">${escapeHtml(displayValue)}</div>`;
                }
            });
            
            html += '</div>';
        } else {
            // Если элемент - просто значение (строка, число и т.д.)
            const displayValue = (item === undefined || item === null) ? '' : String(item);
            if (displayValue) {
                html += `<div class="list-item simple-item">${escapeHtml(displayValue)}</div>`;
            }
        }
    });
    
    html += '</div>';
    return html;
}

// Функция для форматирования сообщения (текст или список)
function formatMessageContent(content) {
    if (content === undefined || content === null) {
        return '<div class="message-text">Нет данных</div>';
    }
    
    // Проверяем, является ли содержимое JSON-массивом
    if (isJSONArray(content)) {
        const jsonArray = getJSONArray(content);
        if (jsonArray && jsonArray.length > 0) {
            return arrayToFormattedList(jsonArray);
        }
    }
    
    // Если это объект (но не массив), показываем его как JSON
    if (typeof content === 'object') {
        return `<pre class="message-json">${escapeHtml(JSON.stringify(content, null, 2))}</pre>`;
    }
    
    // Обычный текст
    return `<div class="message-text">${escapeHtml(String(content))}</div>`;
}

// Функция для добавления сообщения в чат (обновленная)
function addMessage(text, isUser = true, devData = null) {
    const messagesArea = document.getElementById('messagesArea');
    const time = getCurrentTime();
    const messageId = generateMessageId();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
    messageDiv.id = messageId;
    
    // Сохраняем dev данные если есть
    if (devData) {
        devMessagesStorage.set(messageId, devData);
    }
    
    // Формируем содержимое сообщения
    let formattedContent;
    if (isUser) {
        formattedContent = `<div class="message-text">${escapeHtml(String(text))}</div>`;
    } else {
        formattedContent = formatMessageContent(text);
    }
    
    let messageHTML = `
        <div class="message-content">${formattedContent}</div>
        <div class="message-time">${time}</div>
    `;
    
    // Для сообщений ассистента добавляем скрытую кнопку
    if (!isUser) {
        messageHTML += `
            <button class="dev-info-btn hidden" data-message-id="${messageId}">
                🔧 Подробнее
            </button>
            <div class="dev-info-panel hidden" id="devPanel_${messageId}"></div>
        `;
    }
    
    messageDiv.innerHTML = messageHTML;
    messagesArea.appendChild(messageDiv);
    
    // Прокрутка к новому сообщению
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    return messageDiv;
}

// Функция обновления видимости кнопок разработчика
function updateDevButtonsVisibility() {
    const isDevMode = document.getElementById('cb_developers').checked;
    const devButtons = document.querySelectorAll('.dev-info-btn');
    const devPanels = document.querySelectorAll('.dev-info-panel');
    
    devButtons.forEach(btn => {
        if (isDevMode) {
            btn.classList.remove('hidden');
        } else {
            btn.classList.add('hidden');
            const messageId = btn.dataset.messageId;
            const panel = document.getElementById(`devPanel_${messageId}`);
            if (panel) {
                panel.classList.add('hidden');
                panel.innerHTML = '';
            }
        }
    });
}

// Функция для показа/скрытия dev информации
function toggleDevInfo(messageId) {
    const panel = document.getElementById(`devPanel_${messageId}`);
    const devData = devMessagesStorage.get(messageId);
    
    if (!devData) return;
    
    if (panel.classList.contains('hidden')) {
        panel.innerHTML = `
            <div class="dev-info-content">
                <div class="dev-info-header">🔧 ИНФОРМАЦИЯ ДЛЯ РАЗРАБОТЧИКА</div>
                <div class="dev-info-item">
                    <span class="dev-info-label">SQL:</span>
                    <pre class="dev-info-value">${escapeHtml(devData.sql || 'Нет данных')}</pre>
                </div>
                <div class="dev-info-item">
                    <span class="dev-info-label">Контекст:</span>
                    <pre class="dev-info-value">${escapeHtml(devData.context || 'Нет данных')}</pre>
                </div>
                <div class="dev-info-item">
                    <span class="dev-info-label">Функция:</span>
                    <pre class="dev-info-value">${escapeHtml(devData.function || 'Нет данных')}</pre>
                </div>
            </div>
        `;
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
        panel.innerHTML = '';
    }
}

// Функция для отображения индикатора печати
function showTypingIndicator() {
    const messagesArea = document.getElementById('messagesArea');
    
    const indicatorDiv = document.createElement('div');
    indicatorDiv.className = 'message assistant-message';
    indicatorDiv.id = 'typingIndicator';
    
    indicatorDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    
    messagesArea.appendChild(indicatorDiv);
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Функция для удаления индикатора печати
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Обновленная основная функция отправки сообщения
async function submitFunction(event) {
    event.preventDefault();

    const userQuestion = document.getElementById('question');
    const submitButton = document.getElementById('btn_submit');
    const question = userQuestion.value.trim();
    const cb_developers = document.getElementById('cb_developers');

    if (!question) {
        alert('Вы не заполнили поле с вопросом!');
        return;
    }

    if(question == 'Dev'){
        document.getElementById('devContainer').classList.remove('cb_developers_container_hidden');
        document.getElementById('devContainer').classList.add('cb_developers_container_shown');
        alert('Вы вошли в режим разработчика!');
        userQuestion.value = '';
        return;
    }
    else if(question == 'NoDev'){
        cb_developers.checked = false;
        document.getElementById('devContainer').classList.remove('cb_developers_container_shown');
        document.getElementById('devContainer').classList.add('cb_developers_container_hidden');
        updateDevButtonsVisibility();
        userQuestion.value = '';
        return;
    }

    addMessage(question, true);
    userQuestion.value = '';
    submitButton.disabled = true;
    showTypingIndicator();

    try {
        const response = await fetch('/LLM/getllmsqlanswerwithtoolchainrag', {
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                'llm_prompt': question,
                'execute_sql': true
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        removeTypingIndicator();
        
        if (result) {
            const answerContent = result[0];
            const devData = {
                sql: result[3] || 'Нет данных',
                context: result[1] || 'Нет данных',
                function: result[2] || 'Нет данных'
            };
            
            addMessage(answerContent, false, devData);
            
            if (cb_developers.checked) {
                updateDevButtonsVisibility();
            }
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        removeTypingIndicator();
        addMessage('Произошла ошибка. Пожалуйста, попробуйте снова.', false);
        
    } finally {
        submitButton.disabled = false;
        userQuestion.focus();
    }
}

// Функция выполнения SQL
async function submitFunction2(event) {
    event.preventDefault();

    const userQuestion = document.getElementById('sql_question');
    const question = userQuestion.value.trim();

    if (!question) {
        alert('Вы не заполнили поле с SQL!');
        return;
    }

    addMessage(question, true);
    userQuestion.value = '';
    showTypingIndicator();

    try {
        const response = await fetch('/tool/safeexecutesql', {
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                'sql': question,
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        removeTypingIndicator();
        addMessage(result, false);
        
    } catch (error) {
        console.error('Ошибка:', error);
        removeTypingIndicator();
        addMessage('Произошла ошибка. Пожалуйста, попробуйте снова.', false);
        
    } finally {       
        userQuestion.focus();
    }
}

// Функция для обработки клавиши Enter
function handleEnterKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        document.getElementById('QuestionForm').dispatchEvent(new Event('submit'));
    }
}

// Обработчик изменения чекбокса разработчика
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('QuestionForm');
    const questionInput = document.getElementById('question');
    const devCheckbox = document.getElementById('cb_developers');
    
    form.addEventListener('submit', submitFunction);
    questionInput.addEventListener('keydown', handleEnterKey);
    
    if (devCheckbox) {
        devCheckbox.addEventListener('change', updateDevButtonsVisibility);
    }
    
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('dev-info-btn')) {
            const messageId = e.target.dataset.messageId;
            toggleDevInfo(messageId);
        }
    });
    
    addMessage('Здравствуйте! Я AI-ассистент. Задайте мне любой вопрос о данных в базе.', false);
});