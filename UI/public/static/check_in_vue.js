const ticketServiceBaseUrl = 'http://localhost:5004'; // Port for ticket service
const placeholderImage = 'assets/images/placeholder-event.png'; // Default image
const checkInServiceBaseUrl = 'http://localhost:5103'; // now points to check_in_ticket.py
const app = Vue.createApp({
    data() {
        return {
            tickets: [],        // Array to hold fetched tickets
            loading: true,      // Loading state indicator
            error: null,        // Error message holder
            user: null,         // Store logged in user info
            token: null,        // Store auth token
            // Add state for modal/check-in process
            selectedTicketId: null,
            qrCodeDataUrl: null,
            qrStatusMessage: 'Initializing...',
            isCheckingScan: false // To manage polling state later
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
                console.log("[Vue App] Raw Tickets API response:", JSON.stringify(data)); // Log raw response

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
                
                console.log("[Vue App] Extracted ticketsArray before processing:", JSON.stringify(ticketsArray)); // Log extracted array
                
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
        },
        formatImageUrl(imagePath) {
            if (!imagePath) return placeholderImage;
            return imagePath;
        },
        // --- Method to handle Check In button click ---
        async initiateCheckIn(ticketId) {
            console.log(`[Vue App] Initiating check-in for ticket ID: ${ticketId}`);
            this.selectedTicketId = ticketId;
            this.qrCodeDataUrl = null; // Clear previous QR code
            this.qrStatusMessage = 'Generating QR Code...';
            this.isCheckingScan = false; // Reset scan checking flag
            
            // Get modal instance
            const qrModalElement = document.getElementById('qrModal');
            if (!qrModalElement) {
                console.error("[Vue App] QR Modal element not found!");
                this.error = "UI Error: Check-in modal is missing."; // Show error in main UI
                return;
            }
            const qrModal = bootstrap.Modal.getInstance(qrModalElement) || new bootstrap.Modal(qrModalElement);

            qrModal.show(); // Show modal immediately with loading state
        
            try {
                // 3. Call generateQR endpoint (POST)
                const response = await fetch(`${checkInServiceBaseUrl}/generateQR/${this.selectedTicketId}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.token}`,
                        'Accept': 'application/json',
                    },
                });
        
                if (!response.ok) {
                    let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
                    try {
                        const errorData = await response.json();
                        errorMsg = errorData.message || JSON.stringify(errorData);
                    } catch (e) {
                        console.warn("Could not parse error response as JSON.");
                    }
                    throw new Error(errorMsg);
                }
        
                // Handle the response as a binary blob
                const blob = await response.blob(); // Get the response as a Blob (image data)
        
                // Create a URL for the Blob to use as an image source
                this.qrCodeDataUrl = URL.createObjectURL(blob);  // Update Vue data property for image source
        
                console.log("[Vue App] QR Code image received and displayed.");
        
            } catch (error) {
                console.error('[Vue App] Error generating QR code:', error);
                this.qrStatusMessage = `Error: ${error.message}`;
                this.qrCodeDataUrl = null; // Clear QR code on error
            }
        }
        // --- End of initiateCheckIn method ---
        
        // Method for polling will be added later
        // startCheckingScan() { ... }
        // stopCheckingScan() { ... }
    }
});

app.mount('#checkInApp'); 