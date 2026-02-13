async function submitFunction(event) {
    event.preventDefault();

    const form = document.getElementById('Answer');
    const llm_answer = document.getElementById('answer');
    const user_question = document.getElementById('question');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());

    try {

        if (!user_question || !user_question.value.trim()){
            alert('Вы не заполнили поле с вопросом!');
        }

        const response = await fetch('/LLM/getllmanswerwithtoolandchain', {
            method: 'POST',
            headers: {
                'accept': 'application/json',
                'Content-Type': 'application/json' 
            },
            body: JSON.stringify({
                'llm_prompt': user_question.value,
                'execute_sql': false
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (llm_answer) {
            llm_answer.value = result[0];
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Произошла ошибка. Пожалуйста, попробуйте снова.');
    }
}