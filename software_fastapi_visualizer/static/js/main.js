// static/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    const softwareNameEl = document.getElementById('softwareName');
    const softwareIdEl = document.getElementById('softwareId');
    const currentViewEl = document.getElementById('currentView');
    const uiElementsContainer = document.getElementById('ui-elements-container');
    const actionLogUl = document.getElementById('action-log');
    const aiStatusEl = document.getElementById('ai-status');

    let clientSoftwareId = '';

    console.log("Attempting to establish WebSocket connection...");
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws_gui`;
    const guiSocket = new WebSocket(wsUrl);

    guiSocket.onopen = () => {
        console.log('Connected to backend WebSocket for GUI updates.');
        aiStatusEl.textContent = 'Connected to AI control system.';
    };

    guiSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Message from backend:', data);

            if (data.type === 'INIT_DATA') {
                clientSoftwareId = data.software_id;
                aiStatusEl.textContent = `Registered as ${data.software_name || clientSoftwareId}. Waiting for AI...`;
            } else if (data.type === 'UPDATE_CAPABILITIES') {
                clearFormDisplayIfNeeded(); // Clear form if capabilities are being fully re-rendered
                updateUICapabilities(data.payload);
                aiStatusEl.textContent = 'AI is observing. View updated.';
            } else if (data.type === 'EXECUTE_ACTION_VISUALIZATION') {
                const { command, element_id, text, description } = data.payload;
                logAction(`AI: ${command} on '${element_id}' ${text ? `with text "${text}"` : ''}. (Reason: ${description || 'N/A'})`);
                visualizeAction(command, element_id, text);
                aiStatusEl.textContent = `AI action: ${description || command}`;
            } else if (data.type === 'LOG_MESSAGE') {
                logAction(`[SERVER]: ${data.message}`);
            } else if (data.type === 'AI_THOUGHT') {
                aiStatusEl.textContent = `AI is thinking: "${data.message}"`;
            } else if (data.type === 'DISPLAY_FORM_REQUEST') {
                displayFormForUserInput(data.payload);
                aiStatusEl.textContent = `AI needs input for form: ${data.payload.form_description || "Please complete the form."}`;
            } else if (data.type === 'CLEAR_FORM_DISPLAY') {
                clearFormDisplayIfNeeded();
                // aiStatusEl.textContent = "Form submitted. Waiting for AI's next action.";
                // Don't override AI status if it's about to send new capabilities
            }
        } catch (e) {
            console.error("Error processing message from backend:", e, "Raw data:", event.data);
            logAction("[ERROR] Failed to process message from server.");
        }
    };

    guiSocket.onclose = (event) => { /* ... (same as before) ... */
        console.log('Disconnected from backend WebSocket. Was clean:', event.wasClean, 'Code:', event.code, 'Reason:', event.reason);
        aiStatusEl.textContent = 'Disconnected from AI control system.';
        if (!event.wasClean && event.code !== 1000 && event.code !== 1001 ) {
            alert('Connection to server lost unexpectedly. Please refresh. Reason: ' + (event.reason || `Code ${event.code}`));
        }
    };
    guiSocket.onerror = (error) => { /* ... (same as before) ... */
        console.error('WebSocket Error:', error);
        aiStatusEl.textContent = 'Error connecting to AI control system.';
    };


    function handleUserAction(actionData) { /* For clicks on regular UI elements */
        console.log("Attempting to send USER_ACTION (click):", actionData);
        if (guiSocket && guiSocket.readyState === WebSocket.OPEN) {
            guiSocket.send(JSON.stringify({ type: 'USER_ACTION', payload: actionData }));
            logAction(`User action sent: ${actionData.command} on '${actionData.element_id}'`);
        } else { /* ... error handling ... */ }
    }

    function handleUserInput(elementId, value, elementType = 'text_input') { /* For direct input field changes by user */
        console.log(`Attempting to send USER_INPUT_CHANGE: Element ID=${elementId}, Value='${value}', Type=${elementType}`);
        if (guiSocket && guiSocket.readyState === WebSocket.OPEN) {
            guiSocket.send(JSON.stringify({
                type: 'USER_INPUT_CHANGE',
                payload: { element_id: elementId, value: value, element_type: elementType }
            }));
            logAction(`User input on '${elementId}' ('${value}') sent to server.`);
        } else { /* ... error handling ... */ }
    }

    function createUIElement(elementData) {
        // ... (same as the version that creates <input type="text"> for text_input) ...
        // ... and attaches click listeners for 'button' and 'list_item' ...
        const elDiv = document.createElement('div');
        elDiv.classList.add('ui-element');
        const elementType = elementData.type || 'unknown';
        elDiv.classList.add(elementType);
        const elementId = elementData.id || `gen_id_${Math.random().toString(36).substr(2, 9)}`;
        elDiv.id = elementId;
        if (elementData.description) elDiv.setAttribute('data-description', elementData.description);

        const labelStrong = document.createElement('strong');
        labelStrong.textContent = elementData.label || elementId;
        elDiv.appendChild(labelStrong);

        if (elementData.description) {
            const descSpan = document.createElement('span');
            descSpan.className = 'description-text';
            descSpan.textContent = elementData.description;
            elDiv.appendChild(descSpan);
        }

        if (elementType === 'text_input') {
            const inputEl = document.createElement('input');
            inputEl.type = 'text';
            inputEl.className = 'value-input-field';
            inputEl.placeholder = elementData.label || 'Enter text...';
            inputEl.id = `input_for_${elementId}`;
            if (typeof elementData.current_value === 'string') inputEl.value = elementData.current_value;
            inputEl.addEventListener('blur', (event) => handleUserInput(elementId, event.target.value, 'text_input'));
            inputEl.addEventListener('keypress', (event) => {
                if (event.key === 'Enter') { event.preventDefault(); handleUserInput(elementId, event.target.value, 'text_input'); event.target.blur(); }
            });
            elDiv.appendChild(inputEl);
        }

        if (elementType === 'button' || elementType === 'list_item') {
            elDiv.style.cursor = 'pointer';
            elDiv.addEventListener('click', (event) => {
                event.stopPropagation();
                console.log(`Element clicked by user: ID=${elDiv.id}, Type=${elementType}`);
                handleUserAction({ command: 'CLICK', element_id: elDiv.id, description: `User clicked on '${elementData.label || elDiv.id}'` });
            });
        }
        return elDiv;
    }

    function updateUICapabilities(capabilities) {
        // ... (same as before, ensures createUIElement is called for each element) ...
        // ... and sets up view-specific layout containers ...
        console.log("Updating UI with capabilities:", JSON.parse(JSON.stringify(capabilities)));
        if(currentViewEl) currentViewEl.textContent = capabilities.current_view || 'Unknown View';
        if(!uiElementsContainer) { console.error("uiElementsContainer not found!"); return; }
        
        // Do not clear if a form is currently displayed and this is just a minor log update
        if (uiElementsContainer.dataset.showingForm !== 'true' || (capabilities.elements && capabilities.elements.length > 0)) {
            uiElementsContainer.innerHTML = ''; 
            uiElementsContainer.className = 'ui-elements-container';
             if(capabilities.current_view) uiElementsContainer.classList.add(`view-${capabilities.current_view}`);
        }


        if (!capabilities.elements || capabilities.elements.length === 0) {
            if (uiElementsContainer.dataset.showingForm !== 'true') { // Don't overwrite form with this message
                uiElementsContainer.innerHTML = '<p>No interactive elements in this view.</p>';
            }
            return;
        }
        
        if (uiElementsContainer.dataset.showingForm === 'true') {
            // A form is currently displayed, an UPDATE_CAPABILITIES message might be
            // a status update that shouldn't clear the form yet.
            // The backend should send CLEAR_FORM_DISPLAY when appropriate.
            console.log("Form is currently displayed, deferring full capability update until form is cleared.");
            return;
        }

        // --- Layout Logic (same as before) ---
        if (capabilities.current_view === 'homepage') {
            const navButtons = document.createElement('div'); navButtons.className = 'nav-buttons';
            capabilities.elements.forEach(elData => navButtons.appendChild(createUIElement(elData)));
            uiElementsContainer.appendChild(navButtons);
        } else if (capabilities.current_view === 'waimai_page') {
            const searchArea = document.createElement('div'); searchArea.className = 'search-area';
            const foodList = document.createElement('div'); foodList.className = 'food-list';
            const otherControls = document.createElement('div'); otherControls.className = 'other-controls';
            capabilities.elements.forEach(elData => {
                const uiEl = createUIElement(elData);
                if (elData.id && (elData.id.includes('search_food') || elData.id.includes('search_button'))) searchArea.appendChild(uiEl);
                else if (elData.type === 'list_item' || (elData.id && elData.id.includes('food_list'))) foodList.appendChild(uiEl);
                else otherControls.appendChild(uiEl);
            });
            if (searchArea.hasChildNodes()) uiElementsContainer.appendChild(searchArea);
            if (foodList.hasChildNodes()) uiElementsContainer.appendChild(foodList);
            if (otherControls.hasChildNodes()) uiElementsContainer.appendChild(otherControls);
        } else if (capabilities.current_view === 'cart_page') {
            const cartItemsDiv = document.createElement('div'); cartItemsDiv.className = 'cart-items';
            const cartActionsDiv = document.createElement('div'); cartActionsDiv.className = 'cart-actions';
            capabilities.elements.forEach(elData => {
                const uiEl = createUIElement(elData);
                if (elData.type === 'label') cartItemsDiv.appendChild(uiEl);
                else cartActionsDiv.appendChild(uiEl);
            });
            if (cartItemsDiv.hasChildNodes()) uiElementsContainer.appendChild(cartItemsDiv);
            if (cartActionsDiv.hasChildNodes()) uiElementsContainer.appendChild(cartActionsDiv);
        } else if (capabilities.current_view === 'checkout_page') {
            const formArea = document.createElement('div'); formArea.className = 'form-area checkout-form';
            const actionButtons = document.createElement('div'); actionButtons.className = 'action-buttons';
            capabilities.elements.forEach(elData => {
                const uiEl = createUIElement(elData);
                if (elData.type === 'text_input') formArea.appendChild(uiEl);
                else actionButtons.appendChild(uiEl);
            });
            if (formArea.hasChildNodes()) uiElementsContainer.appendChild(formArea);
            if (actionButtons.hasChildNodes()) uiElementsContainer.appendChild(actionButtons);
        }
        else { 
            capabilities.elements.forEach(elData => uiElementsContainer.appendChild(createUIElement(elData)));
        }
        // console.log("UI update complete.");
    }

    function clearFormDisplayIfNeeded() {
        if (uiElementsContainer.dataset.showingForm === 'true') {
            console.log("Clearing displayed form.");
            uiElementsContainer.innerHTML = ''; // Clear form
            uiElementsContainer.dataset.showingForm = 'false';
            // After clearing a form, it's good to re-request/re-render current capabilities
            // if the backend doesn't immediately send an UPDATE_CAPABILITIES.
            // However, our backend flow for USER_FILLED_FORM_DATA -> FORM_DATA_RESPONSE (to AI) -> ACTION_STATUS_UPDATE (from AI) -> UPDATE_CAPABILITIES (to GUI)
            // should handle re-rendering.
        }
    }

    function displayFormForUserInput(formRequestPayload) {
        console.log("Displaying form for user input:", formRequestPayload);
        clearFormDisplayIfNeeded(); // Clear any previous content or form
        uiElementsContainer.innerHTML = ''; // Ensure it's clean
        uiElementsContainer.dataset.showingForm = 'true';

        const formWrapper = document.createElement('div');
        formWrapper.className = 'user-form-wrapper';

        const formTitle = document.createElement('h3');
        formTitle.textContent = formRequestPayload.form_description || "Please complete the form";
        formWrapper.appendChild(formTitle);

        if (formRequestPayload.item_context && formRequestPayload.item_context.name) {
            const contextP = document.createElement('p');
            contextP.innerHTML = `For item: <strong>${formRequestPayload.item_context.name}</strong>`;
            formWrapper.appendChild(contextP);
        }

        const formEl = document.createElement('form');
        formEl.id = 'gui-user-form';

        (formRequestPayload.fields || []).forEach(field => {
            const fieldDiv = document.createElement('div');
            fieldDiv.className = 'form-field';

            const label = document.createElement('label');
            const fieldId = `form_field_${field.id}`;
            label.htmlFor = fieldId;
            label.textContent = field.label || field.id;
            fieldDiv.appendChild(label);

            const fieldType = field.type || 'text'; // Default to text if type is missing

            if (fieldType === 'text' || fieldType === 'number') {
                const input = document.createElement('input');
                input.type = fieldType;
                input.id = fieldId;
                input.name = field.id; // Important for FormData
                if (field.default !== undefined) input.value = field.default;
                if (fieldType === 'number') {
                    if (typeof field.min !== 'undefined') input.min = field.min;
                    if (typeof field.max !== 'undefined') input.max = field.max;
                }
                input.placeholder = field.label || '';
                fieldDiv.appendChild(input);
            } else if (fieldType === 'select' && field.options) {
                const select = document.createElement('select');
                select.id = fieldId;
                select.name = field.id; // Important for FormData
                (field.options || []).forEach(optText => { // Assuming options are simple strings
                    const option = document.createElement('option');
                    option.value = optText;
                    option.textContent = optText;
                    if (optText === field.default) option.selected = true;
                    select.appendChild(option);
                });
                fieldDiv.appendChild(select);
            }
            formEl.appendChild(fieldDiv);
        });

        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.textContent = 'Submit Form';
        submitButton.className = 'ui-element button form-submit-button'; // Add specific class
        formEl.appendChild(submitButton);

        formEl.addEventListener('submit', (event) => {
            event.preventDefault();
            const formData = new FormData(formEl);
            const submittedData = {};
            formData.forEach((value, key) => {
                submittedData[key] = value;
            });
            console.log("User submitted form data via GUI:", submittedData);

            if (guiSocket && guiSocket.readyState === WebSocket.OPEN) {
                guiSocket.send(JSON.stringify({
                    type: 'USER_FILLED_FORM_DATA',
                    payload: {
                        form_data: submittedData,
                        item_context: formRequestPayload.item_context // Send original context back
                    }
                }));
                logAction("User submitted form data: " + JSON.stringify(submittedData));
                // Backend should ideally send CLEAR_FORM_DISPLAY then UPDATE_CAPABILITIES
                // For now, we can optimistically clear and wait for new capabilities.
                // clearFormDisplayIfNeeded(); // Or let backend explicitly command it.
                aiStatusEl.textContent = "Form submitted to AI. Waiting for response...";
            } else { /* ... error handling ... */ }
        });

        formWrapper.appendChild(formEl);
        uiElementsContainer.appendChild(formWrapper);
    }


    function visualizeAction(command, elementId, textToType) {
        // ... (same as before, ensures AI's TYPE_TEXT updates the actual input field) ...
        const targetElementContainer = document.getElementById(elementId);
        if (!targetElementContainer) { console.warn(`Element container with ID '${elementId}' not found for visualization.`); return; }
        targetElementContainer.classList.add('highlight-action');
        setTimeout(() => targetElementContainer.classList.remove('highlight-action'), 700);

        if (command === 'CLICK') {
            targetElementContainer.classList.add('highlight-flash');
            setTimeout(() => targetElementContainer.classList.remove('highlight-flash'), 700);
        } else if (command === 'TYPE_TEXT') {
            const inputField = targetElementContainer.querySelector('.value-input-field');
            if (inputField) {
                inputField.value = textToType;
                console.log(`Visualized AI TYPE_TEXT: Set input field '${inputField.id}' to '${textToType}'`);
            } else { console.warn(`Could not find .value-input-field inside '${elementId}' for AI TYPE_TEXT.`); }
            targetElementContainer.classList.add('highlight-flash');
            setTimeout(() => targetElementContainer.classList.remove('highlight-flash'), 700);
        }
    }

    function logAction(message) { /* ... (same as before) ... */
        if (!actionLogUl) { console.warn("actionLogUl not found for logging:", message); return; }
        const listItem = document.createElement('li');
        listItem.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        actionLogUl.appendChild(listItem);
        actionLogUl.scrollTop = actionLogUl.scrollHeight;
    }
});