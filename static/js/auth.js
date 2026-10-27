// Логика авторизации, регистрации и сессий
function authModule() {
    return {
        authTab: 'login',
        loginForm: { email: '', password: '' },
        registerForm: { full_name: '', email: '', password: '', role: 'applicant' },

        async login() {
            try {
                const res = await fetch('/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.loginForm)
                });
                if (res.ok) {
                    const data = await res.json();
                    this.token = data.access_token;
                    this.user = data.user;
                    localStorage.setItem('token', this.token);
                    localStorage.setItem('user', JSON.stringify(this.user));
                    await this.initDashboard();
                } else {
                    alert('Ошибка входа. Проверьте логин и пароль.');
                }
            } catch (e) {
                console.error(e);
                alert('Не удалось связаться с сервером');
            }
        },

        async register() {
            try {
                const res = await fetch('/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.registerForm)
                });
                if (res.ok) {
                    alert('Регистрация прошла успешно! Теперь войдите.');
                    this.loginForm.email = this.registerForm.email;
                    this.authTab = 'login';
                } else {
                    alert('Ошибка при регистрации.');
                }
            } catch (e) {
                console.error(e);
                alert('Ошибка отправки формы');
            }
        },

        logout() {
            this.token = null;
            this.user = null;
            this.selectedVacancyForHr = null;
            this.myResumes = [];
            this.vacancies = [];
            this.hrVacancies = [];
            this.hrCandidates = [];
            localStorage.removeItem('token');
            localStorage.removeItem('user');
        }
    };
}