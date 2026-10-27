// Логика соискателя: резюме и отклики
function applicantModule() {
    return {
        vacancies: [],
        myResumes: [],
        showApplyModal: false,
        showCreateResumeModal: false,
        selectedVacancy: null,
        selectedResumeId: null,
        coverLetter: '',
        isLoadingResumes: false,

        resumeForm: {
            target_position: '',
            experience_years: '',
            expected_salary: '',
            skills: '',
            employment_type: 'full_time'
        },

        async fetchVacancies() {
            try {
                const res = await fetch('/vacancies/', { headers: this.getHeaders() });
                if (res.ok) {
                    this.vacancies = await res.json();
                }
            } catch (e) {
                console.error('Ошибка загрузки вакансий:', e);
            }
        },

        async fetchMyResumes() {
            this.isLoadingResumes = true;
            try {
                const res = await fetch('/candidates/my-resumes', { headers: this.getHeaders() });
                if (res.ok) {
                    this.myResumes = await res.json();
                    if (this.myResumes.length > 0) {
                        this.selectedResumeId = this.myResumes[0].id;
                    }
                }
            } catch (e) {
                console.error('Ошибка загрузки резюме:', e);
            } finally {
                this.isLoadingResumes = false;
            }
        },

        async createResume() {
            try {
                const res = await fetch('/candidates/resumes', {
                    method: 'POST',
                    headers: this.getHeaders(),
                    body: JSON.stringify({
                        ...this.resumeForm,
                        full_name: this.user.full_name || this.user.email,
                        email: this.user.email
                    })
                });
                if (res.ok) {
                    await this.fetchMyResumes();
                    this.resumeForm = {
                        target_position: '',
                        experience_years: '',
                        expected_salary: '',
                        skills: '',
                        employment_type: 'full_time'
                    };
                    this.showCreateResumeModal = false;
                } else {
                    alert('Ошибка создания резюме.');
                }
            } catch (e) {
                console.error(e);
            }
        },

        openApplyModal(vacancy) {
            this.selectedVacancy = vacancy;
            this.showApplyModal = true;
        },

        async submitApplication() {
            if (!this.selectedResumeId) {
                alert('Выберите резюме перед отправкой.');
                return;
            }
            try {
                const res = await fetch('/candidates/apply', {
                    method: 'POST',
                    headers: this.getHeaders(),
                    body: JSON.stringify({
                        vacancy_id: this.selectedVacancy.id,
                        resume_id: parseInt(this.selectedResumeId),
                        cover_letter: this.coverLetter
                    })
                });
                if (res.ok) {
                    alert('Отклик успешно отправлен!');
                    this.showApplyModal = false;
                    this.coverLetter = '';
                } else {
                    alert('Не удалось отправить отклик.');
                }
            } catch (e) {
                console.error(e);
            }
        }
    };
}