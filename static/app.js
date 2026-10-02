const form = document.querySelector('#student-form');
const dialog = document.querySelector('#success-dialog');
const submitLabel = document.querySelector('#submit-label');
const message = document.querySelector('#form-message');
const params = new URLSearchParams(location.search);
let editToken = params.get('edit') || localStorage.getItem('thuvtm_edit_token');
let editing = false;

function showMessage(text, error = false) {
  message.textContent = text;
  message.classList.toggle('error-message', error);
  message.hidden = false;
}

function clearErrors() {
  document.querySelectorAll('[data-error]').forEach(el => el.textContent = '');
  message.hidden = true;
}

function fillForm(data) {
  ['full_name', 'student_id', 'email', 'reason'].forEach(name => form.elements[name].value = data[name] || '');
  const locationChoice = form.querySelector(`[name="in_hcmc"][value="${data.in_hcmc}"]`);
  const attendanceChoice = form.querySelector(`[name="attendance"][value="${data.attendance}"]`);
  if (locationChoice) locationChoice.checked = true;
  if (attendanceChoice) attendanceChoice.checked = true;
  form.elements.consent.checked = true;
  editing = true;
  submitLabel.textContent = 'Update response';
  showMessage('Your saved response is ready to edit.');
}

async function loadExisting() {
  if (!editToken) return;
  try {
    const response = await fetch(`/api/students/me?token=${encodeURIComponent(editToken)}`);
    if (response.ok) fillForm(await response.json());
    else if (params.has('edit')) showMessage('This private edit link is invalid or no longer available.', true);
  } catch (_) {
    showMessage('Could not load your response. Check your connection and try again.', true);
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearErrors();
  if (!form.elements.consent.checked) {
    document.querySelector('[data-error="consent"]').textContent = 'Please confirm before submitting.';
    return;
  }
  const data = Object.fromEntries(new FormData(form));
  data.in_hcmc = data.in_hcmc === 'true' ? true : data.in_hcmc === 'false' ? false : null;
  delete data.consent;
  if (editing) data.edit_token = editToken;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  submitLabel.textContent = editing ? 'Updating…' : 'Saving…';
  try {
    const response = await fetch(editing ? '/api/students/me' : '/api/students', {
      method: editing ? 'PUT' : 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) {
      Object.entries(result.fields || {}).forEach(([key, value]) => {
        const target = document.querySelector(`[data-error="${key}"]`);
        if (target) target.textContent = value;
      });
      showMessage(result.error || 'Something went wrong. Please try again.', true);
      return;
    }
    if (result.edit_token) {
      editToken = result.edit_token;
      localStorage.setItem('thuvtm_edit_token', result.edit_token);
      const link = `${location.origin}${location.pathname}?edit=${encodeURIComponent(result.edit_token)}`;
      document.querySelector('#edit-link').value = link;
      dialog.showModal();
      history.replaceState(null, '', `${location.pathname}?edit=${encodeURIComponent(result.edit_token)}`);
      editing = true;
    } else {
      showMessage('Your response has been updated successfully.');
    }
  } catch (_) {
    showMessage('Could not connect to the server. Please try again.', true);
  } finally {
    button.disabled = false;
    submitLabel.textContent = editing ? 'Update response' : 'Submit response';
  }
});

document.querySelector('#copy-link').addEventListener('click', async event => {
  await navigator.clipboard.writeText(document.querySelector('#edit-link').value);
  event.currentTarget.textContent = 'Copied';
});
document.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
document.querySelector('.dialog-done').addEventListener('click', () => dialog.close());
loadExisting();
