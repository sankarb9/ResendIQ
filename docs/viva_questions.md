# ResendIQ Viva Questions

### 1. What is ARQ?
Automatic Repeat reQuest; a reliability method using acknowledgements and retransmissions.
### 2. What is an ACK?
An acknowledgement sent by a receiver to confirm packet reception.
### 3. Why is a timeout needed?
The sender cannot wait forever when an ACK may be lost.
### 4. What is Stop-and-Wait?
A protocol that sends one packet and waits for its ACK.
### 5. What is Go-Back-N?
A sliding-window protocol that retransmits from the missing/oldest unacknowledged packet.
### 6. What is Selective Repeat?
A sliding-window protocol that retransmits only packets still unacknowledged.
### 7. What is packet loss?
A simulated event where a data packet does not reach the receiver.
### 8. What is ACK loss?
A simulated event where the acknowledgement does not reach the sender.
### 9. Why use sequence numbers?
To identify packet order and help detect duplicates.
### 10. What is a retransmission?
Sending a packet again after suspected delivery failure.
### 11. What is a sender window?
The set/range of packets the sender may have outstanding.
### 12. What is cumulative ACK?
An ACK confirming receipt up to a point in the packet sequence.
### 13. How does SR handle out-of-order packets?
It can buffer them until missing earlier packets arrive.
### 14. Why suppress duplicates?
A lost ACK may cause a correctly received packet to be sent again.
### 15. What is SHA-256 used for here?
Comparing hashes of original and reconstructed text to check integrity.
### 16. What is a random seed?
A value that makes pseudo-random channel outcomes reproducible.
### 17. Does ResendIQ change real network traffic?
No. It simulates loss in its own software model.
### 18. Is simulated time real latency?
No. It is calculated from simplified configured delays and timeouts.
### 19. What is retransmission overhead?
Retransmission count divided by original packet count, multiplied by 100.
### 20. What does a failed completion mean?
The retry limit was reached or integrity/completion checks did not pass.
### 21. What is the difference between data loss and ACK loss?
Data loss prevents packet reception; ACK loss hides confirmation from the sender.
### 22. What is TCP?
A real transport protocol providing reliable, ordered byte-stream delivery; this project is only a simplified teaching simulation.
### 23. How do the two parts of the project connect?
Measured round-trip loss, RTT and jitter from the Wi-Fi Analyzer are converted into data/ACK loss, one-way delay and timeout for the ARQ simulator.
### 24. Why is per-direction loss 1 - sqrt(1 - L) instead of L?
Ping loss covers the request and the reply. With independent, equal loss p each way, L = 1 - (1 - p)^2, so p = 1 - sqrt(1 - L).
### 25. Why is the timeout RTT + 4 x jitter?
It follows the retransmission-timer idea of mean RTT plus a safety margin for variation; a timeout below one RTT would retransmit needlessly.
### 26. Why run many seeded trials?
One seed is one random outcome; averaging over seeds shows the protocols' typical behaviour.
