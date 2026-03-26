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
    let messageHTML = `
        <div class="message-content">${text}</div>
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
            // Скрываем все открытые панели при выключении dev режима
            const messageId = btn.dataset.messageId;
            const panel = document.getElementById(`devPanel_${messageId}`);
            if (panel) {
                panel.classList.add('hidden');
                panel.innerHTML = ''; // Очищаем содержимое
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
        // Показываем информацию
        panel.innerHTML = `
            <div class="dev-info-content">
                <div class="dev-info-header">🔧 ИНФОРМАЦИЯ ДЛЯ РАЗРАБОТЧИКА</div>
                <div class="dev-info-item">
                    <span class="dev-info-label">SQL:</span>
                    <pre class="dev-info-value">${devData.sql || 'Нет данных'}</pre>
                </div>
                <div class="dev-info-item">
                    <span class="dev-info-label">Контекст:</span>
                    <pre class="dev-info-value">${devData.context || 'Нет данных'}</pre>
                </div>
                <div class="dev-info-item">
                    <span class="dev-info-label">Функция:</span>
                    <pre class="dev-info-value">${devData.function || 'Нет данных'}</pre>
                </div>
            </div>
        `;
        panel.classList.remove('hidden');
    } else {
        // Скрываем информацию
        panel.classList.add('hidden');
        panel.innerHTML = ''; // Очищаем для экономии памяти
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
    
    // Прокрутка к индикатору
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

    // Проверка на пустой вопрос
    if (!question) {
        alert('Вы не заполнили поле с вопросом!');
        return;
    }

    // Специальные команды для разработчика
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
        updateDevButtonsVisibility(); // Обновляем видимость кнопок
        userQuestion.value = '';
        return;
    }

    // Добавляем вопрос пользователя в чат
    addMessage(question, true);
    
    // Очищаем поле ввода
    userQuestion.value = '';
    
    // Блокируем кнопку отправки
    submitButton.disabled = true;
    
    // Показываем индикатор печати
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
        
        // Удаляем индикатор печати
        removeTypingIndicator();
        
        // Добавляем ответ ассистента в чат с dev данными
        if (result) {
            const devData = {
                sql: result[3] || 'Нет данных',
                context: result[1] || 'Нет данных',
                function: result[2] || 'Нет данных'
            };
            
            addMessage(result[0], false, devData);
            
            // Если dev режим уже включен, показываем кнопки для нового сообщения
            if (cb_developers.checked) {
                updateDevButtonsVisibility();
            }
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        
        // Удаляем индикатор печати
        removeTypingIndicator();
        
        // Добавляем сообщение об ошибке
        addMessage('Произошла ошибка. Пожалуйста, попробуйте снова.', false);
        
    } finally {
        // Разблокируем кнопку отправки
        submitButton.disabled = false;
        
        // Возвращаем фокус на поле ввода
        userQuestion.focus();
    }
}

// Функция выполнения SQL
async function submitFunction2(event) {
    event.preventDefault();

    const userQuestion = document.getElementById('sql_question');
    const question = userQuestion.value.trim();

    // Проверка на пустой вопрос
    if (!question) {
        alert('Вы не заполнили поле с SQL!');
        return;
    }

    // Добавляем вопрос пользователя в чат
    addMessage(question, true);
    
    // Очищаем поле ввода
    userQuestion.value = '';
    
    // Показываем индикатор печати
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
        
        // Удаляем индикатор печати
        removeTypingIndicator();
        
        addMessage(result, false);
        
    } catch (error) {
        console.error('Ошибка:', error);
        
        // Удаляем индикатор печати
        removeTypingIndicator();
                // Добавляем сообщение об ошибке
        addMessage('Произошла ошибка. Пожалуйста, попробуйте снова.', false);
        
    } finally {       
        // Возвращаем фокус на поле ввода
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
    
    // Добавляем обработчик отправки формы
    form.addEventListener('submit', submitFunction);
    
    // Добавляем обработчик клавиши Enter
    questionInput.addEventListener('keydown', handleEnterKey);
    
    // Добавляем обработчик изменения чекбокса
    if (devCheckbox) {
        devCheckbox.addEventListener('change', updateDevButtonsVisibility);
    }
    
    // Делегирование событий для кнопок "Подробнее"
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('dev-info-btn')) {
            const messageId = e.target.dataset.messageId;
            toggleDevInfo(messageId);
        }
    });
    
    // Добавляем приветственное сообщение
    addMessage('Здравствуйте! Я AI-ассистент. Задайте мне любой вопрос о данных в базе.', false);
});