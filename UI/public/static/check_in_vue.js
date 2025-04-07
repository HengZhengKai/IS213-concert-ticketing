const ticketServiceBaseUrl = 'http://localhost:5004'; // Port for ticket service
const placeholderImage = 'assets/images/placeholder-event.png'; // Default image

const app = Vue.createApp({
    data() {
        return {
            tickets: [],        // Array to hold fetched tickets
            loading: true,      // Loading state indicator
            error: null,        // Error message holder
            user: null,         // Store logged in user info
            token: null         // Store auth token
        };
    },
    async mounted() {
        console.log("[Vue App] Mounted. Checking session and loading tickets...");
        // 1. Check Session on mount
        if (typeof SessionManager === 'undefined' || !SessionManager.isLoggedIn()) {
            console.error("[Vue App] SessionManager not defined or user not logged in. Redirecting...");
            window.location.href = 'login.html';
            return;
        }
        this.user = SessionManager.getUserSession();
        this.token = localStorage.getItem('token');

        if (!this.user || !this.token) {
            console.error("[Vue App] User/Token missing after login check. Redirecting...");
            SessionManager.clearSession();
            window.location.href = 'login.html';
            return;
        }

        // 2. Load Tickets
        await this.loadUserTickets();
    },
    methods: {
        async loadUserTickets() {
            console.log(`[Vue App] Fetching tickets for userID: ${this.user.userID}`);
            this.loading = true;
            this.error = null;

            try {
                const response = await fetch(`${ticketServiceBaseUrl}/tickets/${this.user.userID}`, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${this.token}`,
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    let errorMsg = `HTTP error! status: ${response.status}`;
                    try {
                        const errorData = await response.json();
                        errorMsg = errorData.message || JSON.stringify(errorData);
                    } catch (e) { console.warn("Could not parse error response as JSON."); }
                    throw new Error(errorMsg);
                }

                const data = await response.json();
                console.log("[Vue App] Tickets API response structure:", data);

                // Extract tickets array based on common API patterns
                let ticketsArray = [];
                if (data && Array.isArray(data.tickets)) {
                    ticketsArray = data.tickets;
                } else if (data && data.data && Array.isArray(data.data.tickets)) {
                    ticketsArray = data.data.tickets;
                } else if (data && data.data && Array.isArray(data.data)) { 
                     ticketsArray = data.data;
                } else if (Array.isArray(data)) {
                    ticketsArray = data;
                } else {
                    console.error("[Vue App] Could not find tickets array in the response:", data);
                }
                
                // *** IMPORTANT: Map API fields to consistent names if needed ***
                this.tickets = ticketsArray.map(ticket => ({
                    ticketID: ticket.ticketID || ticket.ticket_id || null,
                    eventName: ticket.eventName || ticket.event_name || 'Unknown Event',
                    eventDateTime: ticket.eventDateTime || ticket.event_date_time || ticket.date || null,
                    seatNo: ticket.seatNo || ticket.seatNumber || ticket.seat_number || 'N/A',
                    isCheckedIn: ticket.isCheckedIn === true || ticket.is_checked_in === true || ticket.checkedIn === true
                }));
                console.log("[Vue App] Processed tickets for display:", this.tickets);

            } catch (error) {
                console.error('[Vue App] Error loading tickets:', error);
                this.error = `Failed to load tickets: ${error.message}. Please try again later.`;
            } finally {
                this.loading = false;
            }
        },
        formatDateTime(dateTimeString) {
            if (!dateTimeString) return 'No Date';
            try {
                return new Date(dateTimeString).toLocaleString('en-SG', { 
                    year: 'numeric', month: 'numeric', day: 'numeric', 
                    hour: 'numeric', minute: 'numeric', hour12: true 
                });
            } catch (e) {
                console.error("Error formatting date:", dateTimeString, e);
                return 'Invalid Date';
            }
        }
        // Methods for check-in, QR generation etc. will be added later
    }
});

app.mount('#checkInApp'); 