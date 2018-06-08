import React from 'react';
import {Col, Row, Panel, Alert, Table, Glyphicon} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {Stomp} from 'stompjs/lib/stomp.min';
import axios from "axios/index";
import _ from "underscore";
import Form from "react-jsonschema-form";

const InventoryItemSchema = {
    type: "object",
    required: ["barcode", "name", "price"],
    properties: {
      barcode: {type: "string", title: "Barcode"},
      name: {type: "string", title: "Name"},
      price: {type: "number", title: "Price"},
      zone: {
          type: "string",
          title: "Zone"
      },
      lsCode: {type: "string", title: "LS Code"}
    }
};

class StoreInventory extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }


    onNewItemSubmit(submission)
    {
        const newInventoryItem = submission.formData;

        const store = _.clone(this.props.store);
        if (!store.inventory)
        {
            store.inventory = [];
        }

        // Make sure there isn't already an entry for this barcode
        if (_.findWhere(store.inventory, {barcode: newInventoryItem.barcode}))
        {
            alert("Item with this barcode already exists.");
        }
        else
        {
            store.inventory.push(newInventoryItem);
            this.props.updateStore(store);
        }
    }

    render() {
        const storeInventorySchema = _.clone(InventoryItemSchema);
        storeInventorySchema.properties.zone.enum = this.props.store.zones.map((zone) => (zone.id).toString());

        return (
            <div className="store-inventory">
                <br/>
                <Row><Glyphicon glyph="align-left" />
                    <Col md={8}>
                        <Table striped bordered condensed hover>
                            <thead>
                                <tr>
                                    <th>SKU Number</th>
                                    <th>Name</th>
                                    <th>Price</th>
                                    <th>Zone</th>
                                    <th>LS Code</th>
                                </tr>
                            </thead>
                            <tbody>
                            {
                                (this.props.store.inventory) ?
                                    this.props.store.inventory.map((item) =>
                                    {
                                        return <tr key={item.barcode}>
                                            <td>{item.barcode}</td>
                                            <td>{item.name}</td>
                                            <td>{item.price}</td>
                                            <td>{item.zone}</td>
                                            <td>{item.lsCode}</td>
                                        </tr>
                                    })
                                    : null
                            }
                            </tbody>
                        </Table>
                    </Col>
                    <Col md={4}>
                        <h1>New Item</h1>
                        <Form schema={storeInventorySchema}
                              onSubmit={this.onNewItemSubmit.bind(this)} />
                    </Col>
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreInventory);


