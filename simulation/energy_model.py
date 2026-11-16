
import math


class EnergyModel:
    """
    First-Order Radio Energy Model for Wireless Sensor Networks.

    Supports:
        1. Transmission energy
        2. Reception energy
        3. Data aggregation energy
        4. Node residual-energy updates
        5. Dead-node detection
    """

    def __init__(self, config):

        radio = config["radio_model"]

        self.e_elec = float(
            radio["electronics_energy_j_per_bit"]
        )

        self.e_fs = float(
            radio["free_space_energy_j_per_bit_m2"]
        )

        self.e_mp = float(
            radio["multipath_energy_j_per_bit_m4"]
        )

        self.e_da = float(
            radio["data_aggregation_energy_j_per_bit"]
        )

        self.default_packet_size = int(
            config["simulation"]["packet_size_bits"]
        )

        # Validate radio parameters
        parameters = [
            self.e_elec,
            self.e_fs,
            self.e_mp,
            self.e_da
        ]

        if any(not math.isfinite(x) or x < 0 for x in parameters):
            raise ValueError(
                "Energy parameters must be finite and non-negative."
            )

        if self.e_elec <= 0 or self.e_fs <= 0 or self.e_mp <= 0:
            raise ValueError(
                "Electronics, free-space and multipath "
                "coefficients must be positive."
            )

        if self.default_packet_size <= 0:
            raise ValueError("Packet size must be positive.")

        # Calculate distance threshold
        self.d0 = math.sqrt(self.e_fs / self.e_mp)

    def _validate_packet(self, packet_size_bits):

        if (
            not isinstance(packet_size_bits, (int, float))
            or not math.isfinite(packet_size_bits)
            or packet_size_bits <= 0
        ):
            raise ValueError(
                "Packet size must be a positive finite number."
            )

        return float(packet_size_bits)

    def _validate_distance(self, distance):

        if (
            not isinstance(distance, (int, float))
            or not math.isfinite(distance)
            or distance < 0
        ):
            raise ValueError(
                "Distance must be a non-negative finite number."
            )

        return float(distance)

    def transmission_energy(
        self,
        distance,
        packet_size_bits=None
    ):
        """
        Calculate energy required to transmit a packet.
        """

        if packet_size_bits is None:
            packet_size_bits = self.default_packet_size

        L = self._validate_packet(packet_size_bits)
        d = self._validate_distance(distance)

        if d < self.d0:

            energy = L * (
                self.e_elec + self.e_fs * d**2
            )

        else:

            energy = L * (
                self.e_elec + self.e_mp * d**4
            )

        return energy

    def reception_energy(self, packet_size_bits=None):
        """
        Calculate energy required to receive a packet.
        """

        if packet_size_bits is None:
            packet_size_bits = self.default_packet_size

        L = self._validate_packet(packet_size_bits)

        energy = L * self.e_elec

        return energy

    def aggregation_energy(self, total_input_bits):
        """
        Calculate energy required to aggregate incoming data.

        total_input_bits includes all bits processed by
        this aggregation operation.
        """

        L = self._validate_packet(total_input_bits)

        energy = L * self.e_da

        return energy

    def consume_energy(self, node, energy):

        """
        Deduct energy from a sensor node.

        Returns True if the node had sufficient energy.
        Returns False if the node cannot complete the operation.

        If insufficient energy remains, the node is marked dead
        and its residual energy becomes zero.
        """

        if not math.isfinite(energy) or energy < 0:
            raise ValueError(
                "Energy consumption must be non-negative and finite."
            )

        if not node["alive"]:
            return False

        if node["residual_energy"] < energy:

            node["residual_energy"] = 0.0
            node["alive"] = False

            return False

        node["residual_energy"] -= energy

        # Avoid tiny floating-point negative values
        node["residual_energy"] = max(
            0.0,
            node["residual_energy"]
        )

        if node["residual_energy"] <= 0:
            node["alive"] = False

        return node["alive"]

    def transmit(
        self,
        node,
        distance,
        packet_size_bits=None
    ):

        energy = self.transmission_energy(
            distance,
            packet_size_bits
        )

        success = self.consume_energy(
            node,
            energy
        )

        return {
            "success": success,
            "energy_consumed": energy
        }

    def receive(self, node, packet_size_bits=None):

        energy = self.reception_energy(
            packet_size_bits
        )

        success = self.consume_energy(
            node,
            energy
        )

        return {
            "success": success,
            "energy_consumed": energy
        }

    def aggregate(self, node, total_input_bits):

        energy = self.aggregation_energy(
            total_input_bits
        )

        success = self.consume_energy(
            node,
            energy
        )

        return {
            "success": success,
            "energy_consumed": energy
        }

    def print_parameters(self):

        print("\n========== RADIO ENERGY MODEL ==========")

        print(
            "Electronics energy:",
            self.e_elec,
            "J/bit"
        )

        print(
            "Free-space coefficient:",
            self.e_fs,
            "J/bit/m^2"
        )

        print(
            "Multipath coefficient:",
            self.e_mp,
            "J/bit/m^4"
        )

        print(
            "Aggregation energy:",
            self.e_da,
            "J/bit"
        )

        print(
            "Default packet size:",
            self.default_packet_size,
            "bits"
        )

        print(
            "Distance threshold d0:",
            round(self.d0, 3),
            "metres"
        )

        print("========================================\n")
