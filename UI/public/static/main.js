const homeApp = Vue.createApp({
    data() {
        return { 
            events: [],
            loading: true,
            error: null 
        };
    },
    async created() {
        console.log("Vue App is created. Fetching events...");
        try {
            this.events = await fetchEvents();
            console.log("Events fetched:", this.events);
        } catch (error) {
            console.error("Error in created hook:", error);
            this.error = "Failed to load events. Please try again later.";
        } finally {
            this.loading = false;
        }
    }
}).mount("#home");

const buyTicketApp = Vue.createApp({
    data() {
        return { tickets: [], message: "" };
    },
    async created() {
        this.tickets = await fetchAvailableTickets();
    },
    methods: {
        async buyTicket(ticketID) {
            this.message = await buyTicketAPI(ticketID);
        }
    }
}).mount("#buyTicket");

const resaleApp = Vue.createApp({
    data() {
        return { ticketID: "", resaleTicketID: "", price: "", message: "" };
    },
    methods: {
        async buyResaleTicket() {
            this.message = await buyResaleAPI(this.ticketID);
        },
        async resellTicket() {
            this.message = await resellTicketAPI(this.resaleTicketID, this.price);
        }
    }
}).mount("#resale");

const checkinApp = Vue.createApp({
    data() {
        return { ticketID: "", message: "" };
    },
    methods: {
        async checkIn() {
            this.message = await checkInAPI(this.ticketID);
        }
    }
}).mount("#checkin");
