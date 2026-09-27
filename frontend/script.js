'use strict';

// Apply the saved theme before the stylesheet is rendered to prevent a flash.
(() => {
  const savedTheme = localStorage.getItem('neoavlod-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = savedTheme || (prefersDark ? 'dark' : 'light');
})();

const NeoavlodApp = (() => {
  const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
  const UTM_STORAGE_KEY = 'neoavlod-utm';
  const THEME_STORAGE_KEY = 'neoavlod-theme';
  const PHONE_PATTERN = /^\+998 \d{2} \d{3}-\d{2}-\d{2}$/;
  const NAME_PATTERN = /^[\p{L}\p{M}][\p{L}\p{M}\s'‘’`-]{1,49}$/u;

  const elements = {};
  let lastFocusedElement = null;

  function cacheElements() {
    elements.header = document.querySelector('.site-header');
    elements.themeToggle = document.querySelector('.theme-toggle');
    elements.menuToggle = document.querySelector('.menu-toggle');
    elements.mobileMenu = document.querySelector('.mobile-nav');
    elements.form = document.querySelector('#lead-form');
    elements.phone = document.querySelector('#phone');
    elements.course = document.querySelector('#course');
    elements.formStatus = document.querySelector('#form-status');
    elements.submitButton = document.querySelector('.submit-button');
    elements.modal = document.querySelector('#success-modal');
  }

  function initializeTheme() {
    elements.themeToggle.addEventListener('click', () => {
      const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = nextTheme;
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    });
  }

  function initializeHeader() {
    const updateHeader = () => elements.header.classList.toggle('scrolled', window.scrollY > 18);
    updateHeader();
    window.addEventListener('scroll', updateHeader, { passive: true });

    elements.menuToggle.addEventListener('click', () => {
      const isOpening = elements.mobileMenu.hidden;
      elements.mobileMenu.hidden = !isOpening;
      elements.menuToggle.setAttribute('aria-expanded', String(isOpening));
      elements.menuToggle.setAttribute('aria-label', isOpening ? 'Menyuni yopish' : 'Menyuni ochish');
      elements.header.classList.toggle('menu-active', isOpening);
      document.body.classList.toggle('menu-open', isOpening);
    });

    elements.mobileMenu.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', closeMobileMenu);
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth >= 820) closeMobileMenu();
    });
  }

  function closeMobileMenu() {
    elements.mobileMenu.hidden = true;
    elements.menuToggle.setAttribute('aria-expanded', 'false');
    elements.menuToggle.setAttribute('aria-label', 'Menyuni ochish');
    elements.header.classList.remove('menu-active');
    document.body.classList.remove('menu-open');
  }

  function captureUtmParameters() {
    const params = new URLSearchParams(window.location.search);
    const hasIncomingUtm = UTM_KEYS.some((key) => params.has(key));
    let saved = {};

    try {
      saved = JSON.parse(localStorage.getItem(UTM_STORAGE_KEY) || '{}');
    } catch (_error) {
      saved = {};
    }

    if (hasIncomingUtm) {
      UTM_KEYS.forEach((key) => {
        if (params.has(key)) {
          const value = params.get(key)?.trim();
          saved[key] = value || null;
        }
      });
      saved.captured_at = new Date().toISOString();
    }

    if (!saved.utm_source) saved.utm_source = 'organic';
    UTM_KEYS.slice(1).forEach((key) => {
      if (!(key in saved)) saved[key] = null;
    });

    localStorage.setItem(UTM_STORAGE_KEY, JSON.stringify(saved));
    return saved;
  }

  function getStoredUtm() {
    try {
      const stored = JSON.parse(localStorage.getItem(UTM_STORAGE_KEY) || '{}');
      return UTM_KEYS.reduce((result, key) => {
        result[key] = stored[key] ?? (key === 'utm_source' ? 'organic' : null);
        return result;
      }, {});
    } catch (_error) {
      return {
        utm_source: 'organic',
        utm_medium: null,
        utm_campaign: null,
        utm_content: null,
        utm_term: null,
      };
    }
  }

  function formatUzbekPhone(value) {
    let digits = value.replace(/\D/g, '');
    if (digits.startsWith('998')) digits = digits.slice(3);
    digits = digits.slice(0, 9);

    let formatted = '+998';
    if (digits.length > 0) formatted += ` ${digits.slice(0, 2)}`;
    if (digits.length > 2) formatted += ` ${digits.slice(2, 5)}`;
    if (digits.length > 5) formatted += `-${digits.slice(5, 7)}`;
    if (digits.length > 7) formatted += `-${digits.slice(7, 9)}`;
    return formatted;
  }

  function initializePhoneMask() {
    elements.phone.addEventListener('focus', () => {
      if (!elements.phone.value) elements.phone.value = '+998 ';
    });

    elements.phone.addEventListener('input', (event) => {
      event.target.value = formatUzbekPhone(event.target.value);
      clearFieldError(event.target);
    });

    elements.phone.addEventListener('blur', () => {
      if (elements.phone.value.trim() === '+998') elements.phone.value = '';
    });

    elements.phone.addEventListener('keydown', (event) => {
      const cursorAtPrefix = elements.phone.selectionStart <= 5;
      if ((event.key === 'Backspace' || event.key === 'Delete') && cursorAtPrefix) event.preventDefault();
    });
  }

  function setFieldError(input, message) {
    const field = input.closest('.field');
    field.classList.add('has-error');
    input.setAttribute('aria-invalid', 'true');
    const error = field.querySelector('.field-error');
    error.textContent = message;
  }

  function clearFieldError(input) {
    const field = input.closest('.field');
    if (!field) return;
    field.classList.remove('has-error');
    input.removeAttribute('aria-invalid');
    const error = field.querySelector('.field-error');
    if (error) error.textContent = '';
  }

  function validateForm() {
    const firstName = elements.form.elements.first_name;
    const lastName = elements.form.elements.last_name;
    const phone = elements.form.elements.phone;
    const course = elements.form.elements.course;
    let isValid = true;

    [firstName, lastName, phone, course].forEach(clearFieldError);

    if (!NAME_PATTERN.test(firstName.value.trim())) {
      setFieldError(firstName, 'Ism kamida 2 ta harfdan iborat bo‘lishi kerak.');
      isValid = false;
    }
    if (!NAME_PATTERN.test(lastName.value.trim())) {
      setFieldError(lastName, 'Familiya kamida 2 ta harfdan iborat bo‘lishi kerak.');
      isValid = false;
    }
    if (!PHONE_PATTERN.test(phone.value.trim())) {
      setFieldError(phone, 'Raqamni +998 XX XXX-XX-XX formatida to‘liq kiriting.');
      isValid = false;
    }
    if (!course.value) {
      setFieldError(course, 'Qiziqtirgan kursingizni tanlang.');
      isValid = false;
    }

    if (!isValid) {
      const firstInvalid = elements.form.querySelector('[aria-invalid="true"]');
      firstInvalid?.focus();
    }
    return isValid;
  }

  function getApiUrl() {
    const isLocalFrontend = ['localhost', '127.0.0.1'].includes(window.location.hostname)
      && !['8000', ''].includes(window.location.port);
    return isLocalFrontend ? 'http://localhost:8000/api/leads' : '/api/leads';
  }

  async function submitLead(event) {
    event.preventDefault();
    elements.formStatus.className = 'form-status';
    elements.formStatus.textContent = '';
    if (!validateForm()) return;

    const formData = new FormData(elements.form);
    const payload = {
      first_name: formData.get('first_name').trim(),
      last_name: formData.get('last_name').trim(),
      phone: formData.get('phone').trim(),
      course: formData.get('course'),
      ...getStoredUtm(),
    };

    setSubmitting(true);
    try {
      const response = await fetch(getApiUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
      });

      let result = {};
      try {
        result = await response.json();
      } catch (_error) {
        result = {};
      }

      if (!response.ok) {
        throw new Error(result.detail || 'Arizani yuborishda xatolik yuz berdi.');
      }

      elements.form.reset();
      openSuccessModal();
    } catch (error) {
      elements.formStatus.className = 'form-status error';
      elements.formStatus.textContent = error.message === 'Failed to fetch'
        ? 'Server bilan aloqa o‘rnatilmadi. Internetni tekshirib, qayta urinib ko‘ring.'
        : error.message;
    } finally {
      setSubmitting(false);
    }
  }

  function setSubmitting(isSubmitting) {
    elements.submitButton.disabled = isSubmitting;
    elements.submitButton.classList.toggle('is-loading', isSubmitting);
    elements.submitButton.querySelector('span').textContent = isSubmitting ? 'Yuborilmoqda…' : 'Arizani yuborish';
  }

  function initializeForm() {
    elements.form.addEventListener('submit', submitLead);
    elements.form.querySelectorAll('input, select').forEach((input) => {
      input.addEventListener('change', () => clearFieldError(input));
      if (input.type === 'text') input.addEventListener('input', () => clearFieldError(input));
    });

    document.querySelectorAll('.choose-course').forEach((button) => {
      button.addEventListener('click', () => {
        elements.course.value = button.dataset.course;
        clearFieldError(elements.course);
        document.querySelector('#admission').scrollIntoView({ behavior: 'smooth' });
        window.setTimeout(() => elements.form.elements.first_name.focus({ preventScroll: true }), 700);
      });
    });
  }

  function openSuccessModal() {
    lastFocusedElement = document.activeElement;
    elements.modal.hidden = false;
    document.body.classList.add('modal-open');
    elements.modal.querySelector('button[data-close-modal]').focus();
  }

  function closeSuccessModal() {
    elements.modal.hidden = true;
    document.body.classList.remove('modal-open');
    lastFocusedElement?.focus();
  }

  function initializeModal() {
    elements.modal.querySelectorAll('[data-close-modal]').forEach((element) => {
      element.addEventListener('click', closeSuccessModal);
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !elements.modal.hidden) closeSuccessModal();
    });
  }

  function initializeRevealAnimations() {
    const revealElements = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      revealElements.forEach((element) => element.classList.add('is-visible'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -35px' });

    revealElements.forEach((element, index) => {
      element.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
      observer.observe(element);
    });
  }

  function initialize() {
    cacheElements();
    captureUtmParameters();
    initializeTheme();
    initializeHeader();
    initializePhoneMask();
    initializeForm();
    initializeModal();
    initializeRevealAnimations();
    document.querySelector('#current-year').textContent = new Date().getFullYear();
  }

  return { initialize };
})();

document.addEventListener('DOMContentLoaded', NeoavlodApp.initialize);
