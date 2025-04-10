const ticketServiceBaseUrl = 'http://localhost:5004'; // Port for ticket service
const placeholderImage = 'assets/images/placeholder-event.png'; // Default image
const checkInServiceBaseUrl = 'http://localhost:5103'; // now points to check_in_ticket.py
const kongBaseUrl = "http://localhost:8000";
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
            isCheckingScan: false, // Potentially redundant now, but can keep
            pollingIntervalId: null, // To store the polling timer
            qrModalInstance: null // To store modal instance
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

        // Setup Modal Listener when component mounts
        this.setupModalListener();

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
        setupModalListener() {
            const qrModalElement = document.getElementById('qrModal');
            if (qrModalElement) {
                // Listen for the modal being hidden
                qrModalElement.addEventListener('hidden.bs.modal', () => {
                    console.log('[Vue App] QR Modal hidden. Stopping polling.');
                    this.stopPollingStatus();
                    // Clean up QR code URL to free memory
                    if (this.qrCodeDataUrl) {
                        URL.revokeObjectURL(this.qrCodeDataUrl);
                        this.qrCodeDataUrl = null;
                    }
                });
            } else {
                console.error('[Vue App] Could not find qrModal element to attach hide listener.');
            }
        },
        async initiateCheckIn(ticketId) {
            console.log(`[Vue App] Initiating check-in for ticket ID: ${ticketId}`);
            this.selectedTicketId = ticketId;
            this.qrCodeDataUrl = null; 
            this.qrStatusMessage = 'Generating QR Code...';
            this.stopPollingStatus(); // Stop any previous polling
            
            const qrModalElement = document.getElementById('qrModal');
            if (!qrModalElement) {
                console.error("[Vue App] QR Modal element not found!");
                this.error = "UI Error: Check-in modal is missing.";
                return;
            }
            // Store the instance if not already stored or get existing one
            this.qrModalInstance = bootstrap.Modal.getInstance(qrModalElement) || new bootstrap.Modal(qrModalElement);

            this.qrModalInstance.show(); // Show modal
        
            try {
                // 3. Call generateQR endpoint (GET)
                const response = await fetch(`${checkInServiceBaseUrl}/generateqr/${this.selectedTicketId}`, {
                    method: 'GET' 
                });
        
                if (!response.ok) {
                    let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
                    try {
                        const errorText = await response.text(); 
                        errorMsg = errorText;
                    } catch (e) {
                        console.warn("Could not read/parse error response body.");
                    }
                    throw new Error(errorMsg);
                }
        
                const blob = await response.blob();
                this.qrCodeDataUrl = URL.createObjectURL(blob);
                this.qrStatusMessage = 'Scan the QR code below.';
                console.log("[Vue App] QR Code image received. Starting polling...");
                
                // Start polling for status updates
                this.startPollingStatus(); 
        
            } catch (error) {
                console.error('[Vue App] Error generating QR code:', error);
                this.qrStatusMessage = `Error: ${error.message}`;
                this.qrCodeDataUrl = null;
            }
        },
        startPollingStatus() {
            this.stopPollingStatus(); // Ensure no duplicate intervals
            console.log(`[Vue App] Starting status polling for ${this.selectedTicketId}`);
            this.isCheckingScan = true; // Indicate polling is active
            // Poll every 2 seconds (adjust as needed)
            this.pollingIntervalId = setInterval(this.checkScanStatus, 2000);
            // Optionally run immediate check
            // this.checkScanStatus(); 
        },
        stopPollingStatus() {
            if (this.pollingIntervalId) {
                console.log(`[Vue App] Stopping status polling for ${this.selectedTicketId}`);
                clearInterval(this.pollingIntervalId);
                this.pollingIntervalId = null;
                this.isCheckingScan = false; // Indicate polling stopped
            }
        },
        async checkScanStatus() {
            if (!this.selectedTicketId) {
                console.warn('[Vue App] checkScanStatus called without selectedTicketId');
                this.stopPollingStatus();
                return;
            }
            console.log(`[Vue App] Polling status for ${this.selectedTicketId}...`);
            try {
                const response = await fetch(`${checkInServiceBaseUrl}/checkstatus/${this.selectedTicketId}`, {
                    method: 'GET'
                });
                if (!response.ok) {
                    console.error(`[Vue App] Polling error: HTTP ${response.status}`);
                    return; 
                }
                const data = await response.json();
                console.log(`[Vue App] Poll status received: ${data.status}`);

                if (data.status === 'checked_in') {
                    console.log(`[Vue App] Ticket ${this.selectedTicketId} confirmed checked in! Redirecting...`);
                    this.stopPollingStatus();
                    if (this.qrModalInstance) {
                         this.qrModalInstance.hide(); // Hide modal before redirect
                    }
                    
                    // Redirect the main window to the success page
                    window.location.href = `${checkInServiceBaseUrl}/success`; 
                    
                    // No need to reload tickets here as we are navigating away
                    // await this.loadUserTickets(); 
                }
                // If status is 'not_yet', do nothing

            } catch (error) {
                console.error('[Vue App] Error during status polling fetch:', error);
            }
        }
    }
});

app.mount('#checkInApp'); 