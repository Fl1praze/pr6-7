// Логика HR / Работодателя
function employerModule() {
    return {
        hrVacancies: [],
        selectedVacancyForHr: null,
        hrCandidates: [],

        async fetchHrVacancies() {
            try {
                const res = await fetch('/vacancies/', { headers: this.getHeaders() });
                if (res.ok) {
                    this.hrVacancies = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        },

        selectVacancyForHr(vacancy) {
            this.selectedVacancyForHr = vacancy;
            this.fetchHrCandidates();
        },

        async fetchHrCandidates() {
            if (!this.selectedVacancyForHr) return;
            try {
                const res = await fetch(`/vacancies/${this.selectedVacancyForHr.id}/candidates`, {
                    headers: this.getHeaders()
                });
                if (res.ok) {
                    this.hrCandidates = await res.json();
                }
            } catch (e) {
                console.error(e);
            }
        }
    };
}